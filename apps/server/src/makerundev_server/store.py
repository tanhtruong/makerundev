import hashlib
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from makerundev import Activity, Sport, load
from makerundev.metrics import summarize, trimp
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from makerundev_server.db import ActivityRow, AthleteSettingsRow
from makerundev_server.settings import AthleteSettings, TrimpCoefficients, ZoneModel

SETTINGS_ID = 1
log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ImportResult:
    activity_id: int
    created: bool


@dataclass(frozen=True, slots=True)
class SaveResult:
    recomputed: int
    unreadable: int


class Store:
    def __init__(self, data_dir: Path, engine: Engine) -> None:
        self.engine = engine
        self.writing = threading.Lock()
        self.originals = data_dir / "originals"
        self.streams = data_dir / "streams"
        self.originals.mkdir(parents=True, exist_ok=True)
        self.streams.mkdir(parents=True, exist_ok=True)

    def import_file(self, filename: str, data: bytes) -> ImportResult:
        digest = hashlib.sha256(data).hexdigest()
        with self.writing, Session(self.engine) as session:
            existing = session.scalar(select(ActivityRow.id).where(ActivityRow.sha256 == digest))
            if existing is not None:
                return ImportResult(existing, created=False)
            activity = load(data)
            summary = summarize(activity)
            settings = _settings(session)
            row = ActivityRow(
                sha256=digest,
                storage_key=digest,
                filename=Path(filename).name[:255] or "upload",
                source_format=activity.source_format,
                sport=activity.sport.value,
                device=activity.device,
                start_time=activity.start_time,
                distance_m=summary.distance_m,
                elapsed_s=summary.elapsed_s,
                moving_s=summary.moving_s,
                pace_s_per_km=summary.pace_s_per_km,
                avg_heart_rate=summary.avg_heart_rate,
                max_heart_rate=summary.max_heart_rate,
                elevation_gain_m=summary.elevation_gain_m,
                trimp=_trimp(activity, settings) if settings else None,
            )
            session.add(row)
            session.flush()
            (self.originals / digest).write_bytes(data)
            activity.records.write_parquet(self.streams / f"{digest}.parquet")
            session.commit()
            return ImportResult(row.id, created=True)

    def list(self) -> list[ActivityRow]:
        with Session(self.engine) as session:
            return list(
                session.scalars(select(ActivityRow).order_by(ActivityRow.start_time.desc()))
            )

    def get(self, activity_id: int) -> ActivityRow | None:
        with Session(self.engine) as session:
            return session.get(ActivityRow, activity_id)

    def records(self, row: ActivityRow) -> pl.DataFrame:
        return pl.read_parquet(self.streams / f"{row.storage_key}.parquet")

    def activity(self, row: ActivityRow) -> Activity:
        return Activity(
            sport=Sport(row.sport), start_time=row.start_time, records=self.records(row)
        )

    def highest_heart_rate(self) -> float | None:
        with Session(self.engine) as session:
            return session.scalar(select(func.max(ActivityRow.max_heart_rate)))

    def athlete_settings(self) -> AthleteSettings | None:
        with Session(self.engine) as session:
            return _settings(session)

    def save_athlete_settings(self, settings: AthleteSettings) -> SaveResult:
        with self.writing, Session(self.engine) as session:
            previous = _settings(session)
            recomputed = unreadable = 0
            if previous is None or previous.trimp_inputs() != settings.trimp_inputs():
                for row in session.scalars(select(ActivityRow)):
                    try:
                        activity = self.activity(row)
                    except (OSError, pl.exceptions.PolarsError) as error:
                        log.warning("cannot read the stream of activity %s: %s", row.id, error)
                        row.trimp = None
                        unreadable += 1
                        continue
                    row.trimp = _trimp(activity, settings)
                    recomputed += 1
            session.merge(
                AthleteSettingsRow(
                    id=SETTINGS_ID,
                    max_hr=settings.max_hr,
                    resting_hr=settings.resting_hr,
                    trimp_coefficients=settings.trimp_coefficients.value,
                    timezone=settings.timezone,
                    zone_model=settings.zone_model.value,
                    zone_thresholds=list(settings.zone_thresholds),
                )
            )
            session.commit()
            return SaveResult(recomputed=recomputed, unreadable=unreadable)


def _settings(session: Session) -> AthleteSettings | None:
    row = session.get(AthleteSettingsRow, SETTINGS_ID)
    if row is None:
        return None
    return AthleteSettings(
        max_hr=row.max_hr,
        resting_hr=row.resting_hr,
        trimp_coefficients=TrimpCoefficients(row.trimp_coefficients),
        timezone=row.timezone,
        zone_model=ZoneModel(row.zone_model),
        zone_thresholds=tuple(row.zone_thresholds),
    )


def _trimp(activity: Activity, settings: AthleteSettings) -> float | None:
    heart_rate = activity.records["heart_rate"]
    if heart_rate.is_nan().fill_null(True).all():
        return None
    return trimp(activity, settings.resting_hr, settings.max_hr, settings.coefficients)

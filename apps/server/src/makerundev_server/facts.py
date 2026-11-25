import datetime as dt
import gzip
import json
import logging
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
from makerundev import Activity, ActivityFileError, Lap, Sport, load
from makerundev.metrics import best_efforts, summarize, trimp
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from makerundev_server.db import ActivityRow
from makerundev_server.settings import AthleteSettings

FACTS_VERSION = 1
RUNNING_DYNAMICS = ("ground_contact_time", "vertical_oscillation", "step_length")

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Refreshed:
    recomputed: int
    unreadable: int


class StoredFacts:
    def __init__(self, data_dir: Path) -> None:
        self.originals = data_dir / "originals"
        self.streams = data_dir / "streams"
        self.originals.mkdir(parents=True, exist_ok=True)
        self.streams.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        session: Session,
        row: ActivityRow,
        activity: Activity,
        original: bytes,
        settings: AthleteSettings | None,
    ) -> None:
        row.source_format = activity.source_format
        row.sport = activity.sport.value
        row.device = activity.device
        row.start_time = activity.start_time
        row.laps = _encode_laps(activity.laps)
        _derive(row, activity, settings)
        session.add(row)
        session.flush()
        (self.originals / row.storage_key).write_bytes(original)
        activity.records.write_parquet(self._stream(row))

    def keep_strava_laps(self, row: ActivityRow, listed: Any, laps: tuple[Lap, ...]) -> None:
        if listed is not None:
            path = self.originals / row.storage_key
            try:
                original = json.loads(gzip.decompress(path.read_bytes()))
                original["activity"]["laps"] = listed
                _replace(path, lambda temporary: temporary.write_bytes(_gzip_json(original)))
            except (OSError, ValueError) as error:
                log.warning(
                    "cannot store the laps of activity %s in its original: %s", row.id, error
                )
        row.laps = _encode_laps(laps)

    def refresh_trimp(self, session: Session, settings: AthleteSettings) -> Refreshed:
        recomputed = unreadable = 0
        for row in session.scalars(select(ActivityRow)):
            try:
                activity = self.read(row)
            except (OSError, pl.exceptions.PolarsError) as error:
                log.warning("cannot read the stream of activity %s: %s", row.id, error)
                row.trimp = None
                unreadable += 1
                continue
            row.trimp = _trimp(activity, settings)
            recomputed += 1
        return Refreshed(recomputed=recomputed, unreadable=unreadable)

    def catch_up(self, engine: Engine, settings: AthleteSettings | None) -> int:
        with Session(engine) as session:
            behind = session.scalars(
                select(ActivityRow.id).where(ActivityRow.facts_version < FACTS_VERSION)
            ).all()
        for activity_id in behind:
            with Session(engine) as session:
                row = session.get(ActivityRow, activity_id)
                if row is None:
                    continue
                try:
                    self._catch_up(row, settings)
                except Exception:
                    log.exception(
                        "activity %s could not catch up; its missing facts stay empty", row.id
                    )
                row.facts_version = FACTS_VERSION
                session.commit()
        return len(behind)

    def read(self, row: ActivityRow) -> Activity:
        return _activity(row, self.records(row))

    def records(self, row: ActivityRow) -> pl.DataFrame:
        return pl.read_parquet(self._stream(row))

    def remove(self, storage_key: str) -> None:
        (self.originals / storage_key).unlink(missing_ok=True)
        (self.streams / f"{storage_key}.parquet").unlink(missing_ok=True)

    def _stream(self, row: ActivityRow) -> Path:
        return self.streams / f"{row.storage_key}.parquet"

    def _catch_up(self, row: ActivityRow, settings: AthleteSettings | None) -> None:
        records = self.records(row)
        original = self._original(row) if row.sha256 is not None else None
        if row.source_format == "fit" and not set(RUNNING_DYNAMICS) <= set(records.columns):
            records = records.with_columns(_dynamics(row, records, original))
            _replace(self._stream(row), records.write_parquet)
        if original is not None:
            row.laps = _encode_laps(original.laps)
        elif row.sha256 is not None and row.laps is None:
            row.laps = []
        _derive(row, _activity(row, records), settings)

    def _original(self, row: ActivityRow) -> Activity | None:
        try:
            return load(self.originals / row.storage_key)
        except (OSError, ActivityFileError) as error:
            log.warning("cannot read the original of activity %s: %s", row.id, error)
            return None


def _activity(row: ActivityRow, records: pl.DataFrame) -> Activity:
    return Activity(
        sport=Sport(row.sport),
        start_time=row.start_time,
        records=records,
        laps=_decode_laps(row.laps or []),
    )


def _derive(row: ActivityRow, activity: Activity, settings: AthleteSettings | None) -> None:
    summary = summarize(activity)
    row.distance_m = summary.distance_m
    row.elapsed_s = summary.elapsed_s
    row.moving_s = summary.moving_s
    row.pace_s_per_km = summary.pace_s_per_km
    row.avg_heart_rate = summary.avg_heart_rate
    row.max_heart_rate = summary.max_heart_rate
    row.elevation_gain_m = summary.elevation_gain_m
    row.trimp = _trimp(activity, settings) if settings else None
    row.best_efforts = [
        {"distance_m": distance, "elapsed_s": seconds}
        for distance, seconds in best_efforts(activity).items()
    ]
    row.facts_version = FACTS_VERSION


def _dynamics(
    row: ActivityRow, stored: pl.DataFrame, original: Activity | None
) -> tuple[pl.Series, ...]:
    if original is not None:
        parsed = original.records
        if parsed.height == stored.height and parsed["timestamp"].equals(stored["timestamp"]):
            return tuple(parsed[name].cast(pl.Float64) for name in RUNNING_DYNAMICS)
        log.warning(
            "the original of activity %s no longer matches its stream; running dynamics left empty",
            row.id,
        )
    return tuple(pl.Series(name, [None] * stored.height, pl.Float64) for name in RUNNING_DYNAMICS)


def _trimp(activity: Activity, settings: AthleteSettings) -> float | None:
    return trimp(activity, settings.resting_hr, settings.max_hr, settings.coefficients)


def _gzip_json(value: Any) -> bytes:
    return gzip.compress(json.dumps(value).encode())


def _replace(path: Path, write: Callable[[Path], object]) -> None:
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        write(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _encode_laps(laps: tuple[Lap, ...]) -> list[dict[str, Any]]:
    return [
        {
            "start_time": lap.start_time.isoformat(),
            "elapsed_s": lap.elapsed_s,
            "distance_m": lap.distance_m,
        }
        for lap in laps
    ]


def _decode_laps(stored: list[dict[str, Any]]) -> tuple[Lap, ...]:
    return tuple(
        Lap(
            start_time=dt.datetime.fromisoformat(lap["start_time"]),
            elapsed_s=lap["elapsed_s"],
            distance_m=lap["distance_m"],
        )
        for lap in stored
    )

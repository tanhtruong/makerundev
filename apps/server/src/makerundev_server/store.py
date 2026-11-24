import datetime as dt
import gzip
import hashlib
import json
import logging
import os
import threading
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
from makerundev import Activity, ActivityFileError, Lap, Sport, load
from makerundev.io import unzip
from makerundev.metrics import Summary, summarize, trimp
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from makerundev_server.db import (
    STRAVA,
    ActivityRow,
    AthleteSettingsRow,
    GarminConnectionRow,
    Outcome,
    StravaConnectionRow,
    SyncState,
    activity_name,
)
from makerundev_server.garmin_store import GarminStore
from makerundev_server.listing import ActivityFilter, ActivitySort, conditions, ordering
from makerundev_server.matching import file_match, synced_match
from makerundev_server.performance_store import PerformanceStore, stored_efforts
from makerundev_server.settings import AthleteSettings, TrimpCoefficients, ZoneModel
from makerundev_server.strava import Tokens, Unauthorized
from makerundev_server.sync_state import (
    CONNECTION_ID,
    Phase,
    advance,
    begin_sync,
    end_sync,
    record_skip,
    skipped_entry,
)

SETTINGS_ID = 1
RUNNING_DYNAMICS = ("ground_contact_time", "vertical_oscillation", "step_length")

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
        self.garmin = GarminStore(engine, self.writing)
        self.performance = PerformanceStore(engine, self.writing, self.activity)

    def import_file(self, filename: str, data: bytes, name: str | None = None) -> ImportResult:
        entry = unzip(data)
        if entry is not None:
            filename, data = entry
        digest = hashlib.sha256(data).hexdigest()
        with self.writing, Session(self.engine) as session:
            existing = session.scalar(select(ActivityRow.id).where(ActivityRow.sha256 == digest))
            if existing is not None:
                return ImportResult(existing, created=False)
            activity = load(data)
            summary = summarize(activity)
            basename = Path(filename).name[:255] or "upload"
            synced = synced_match(session, basename, activity.start_time, summary.distance_m)
            replaced = synced.storage_key if synced is not None else None
            row = synced if synced is not None else ActivityRow()
            row.sha256 = digest
            row.storage_key = digest
            row.filename = basename
            row.name = row.name or activity_name(name) or activity_name(activity.name)
            _describe(row, activity, summary, _settings(session))
            session.add(row)
            session.flush()
            (self.originals / digest).write_bytes(data)
            activity.records.write_parquet(self.streams / f"{digest}.parquet")
            session.commit()
            if replaced is not None:
                self._remove_files(replaced)
            return ImportResult(row.id, created=True)

    def list(self) -> list[ActivityRow]:
        with Session(self.engine) as session:
            return list(
                session.scalars(select(ActivityRow).order_by(ActivityRow.start_time.desc()))
            )

    def page(
        self,
        limit: int,
        offset: int,
        wanted: ActivityFilter,
        sort: ActivitySort,
    ) -> tuple[Sequence[ActivityRow], int]:
        where = conditions(wanted)
        listed = select(ActivityRow).where(*where).order_by(*ordering(sort))
        counted = select(func.count()).select_from(ActivityRow).where(*where)
        with Session(self.engine) as session:
            rows = session.scalars(listed.limit(limit).offset(offset)).all()
            total = session.scalar(counted) or 0
        return rows, total

    def get(self, activity_id: int) -> ActivityRow | None:
        with Session(self.engine) as session:
            return session.get(ActivityRow, activity_id)

    def records(self, row: ActivityRow) -> pl.DataFrame:
        path = self.streams / f"{row.storage_key}.parquet"
        records = pl.read_parquet(path)
        if row.source_format != "fit" or set(RUNNING_DYNAMICS) <= set(records.columns):
            return records
        records = records.with_columns(self._original_dynamics(row, records))
        try:
            _replace_parquet(records, path)
        except OSError as error:
            log.warning("cannot store the running dynamics of activity %s: %s", row.id, error)
        return records

    def _original_dynamics(self, row: ActivityRow, stored: pl.DataFrame) -> tuple[pl.Series, ...]:
        try:
            parsed = load(self.originals / row.storage_key).records
        except (OSError, ActivityFileError) as error:
            log.warning("cannot read the running dynamics of activity %s: %s", row.id, error)
        else:
            if parsed.height == stored.height and parsed["timestamp"].equals(stored["timestamp"]):
                return tuple(parsed[name].cast(pl.Float64) for name in RUNNING_DYNAMICS)
            log.warning(
                "the original of activity %s no longer matches its stream; "
                "running dynamics left empty",
                row.id,
            )
        return tuple(
            pl.Series(name, [None] * stored.height, pl.Float64) for name in RUNNING_DYNAMICS
        )

    def activity(self, row: ActivityRow) -> Activity:
        return Activity(
            sport=Sport(row.sport),
            start_time=row.start_time,
            records=self.records(row),
            laps=_decode_laps(row.laps or []),
        )

    def laps(self, row: ActivityRow) -> tuple[Lap, ...]:
        if row.laps is not None:
            return _decode_laps(row.laps)
        if row.sha256 is None:
            return ()
        with self.writing, Session(self.engine) as session:
            stored = session.get(ActivityRow, row.id)
            if stored is None:
                return ()
            if stored.laps is None:
                stored.laps = _encode_laps(self._original_laps(stored))
                session.commit()
            return _decode_laps(stored.laps)

    def _original_laps(self, row: ActivityRow) -> tuple[Lap, ...]:
        if row.sha256 is None:
            return ()
        try:
            return load(self.originals / row.storage_key).laps
        except (OSError, ActivityFileError) as error:
            log.warning("cannot read the laps of activity %s: %s", row.id, error)
            return ()

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
                    body_mass_kg=settings.body_mass_kg,
                )
            )
            session.commit()
            return SaveResult(recomputed=recomputed, unreadable=unreadable)

    def strava_connection(self) -> StravaConnectionRow | None:
        with Session(self.engine) as session:
            return session.get(StravaConnectionRow, CONNECTION_ID)

    def begin_strava_oauth(self, state: str) -> None:
        with self.writing, Session(self.engine) as session:
            _connection(session).oauth_state = state
            session.commit()

    def save_strava_tokens(self, tokens: Tokens) -> None:
        with self.writing, Session(self.engine) as session:
            row = _connection(session)
            row.oauth_state = None
            row.access_token = tokens.access_token
            row.refresh_token = tokens.refresh_token
            row.expires_at = tokens.expires_at
            session.commit()

    def start_strava_sync(self) -> bool:
        with self.writing, Session(self.engine) as session:
            row = session.get(StravaConnectionRow, CONNECTION_ID)
            if row is None or row.access_token is None or row.syncing:
                return False
            begin_sync(row)
            session.commit()
            return True

    def finish_strava_sync(self, outcome: Outcome) -> None:
        with self.writing, Session(self.engine) as session:
            row = session.get(StravaConnectionRow, CONNECTION_ID)
            if row is not None:
                end_sync(row, outcome)
                session.commit()

    def reset_syncs(self) -> None:
        with self.writing, Session(self.engine) as session:
            rows: list[SyncState | None] = [
                session.get(StravaConnectionRow, CONNECTION_ID),
                session.get(GarminConnectionRow, CONNECTION_ID),
            ]
            for row in rows:
                if row is not None and row.syncing:
                    row.syncing = False
                    row.sync_outcome = "interrupted"
                    row.resume_at = None
            session.commit()

    def finish_strava_backfill(self) -> None:
        with self.writing, Session(self.engine) as session:
            _connected(session).backfill_done = True
            session.commit()

    def claim_strava(self, summary: Mapping[str, Any], start: dt.datetime, phase: Phase) -> bool:
        strava_id = str(summary["id"])
        with self.writing, Session(self.engine) as session:
            known = session.scalar(
                select(ActivityRow.id).where(
                    ActivityRow.external_source == STRAVA, ActivityRow.external_id == strava_id
                )
            )
            connection = _connected(session)
            if known is None:
                distance = float(summary.get("distance") or 0.0)
                file_row = file_match(session, strava_id, start, distance)
                if file_row is None:
                    return False
                file_row.external_source = STRAVA
                file_row.external_id = strava_id
                file_row.name = activity_name(summary.get("name")) or file_row.name
                connection.matched += 1
            advance(connection, phase, start)
            session.commit()
            return True

    def add_strava(
        self,
        summary: Mapping[str, Any],
        streams: Mapping[str, Any],
        activity: Activity,
        phase: Phase,
    ) -> None:
        strava_id = str(summary["id"])
        key = f"strava-{strava_id}"
        original = gzip.compress(json.dumps({"activity": summary, "streams": streams}).encode())
        described = summarize(activity)
        with self.writing, Session(self.engine) as session:
            row = ActivityRow(
                storage_key=key,
                external_source=STRAVA,
                external_id=strava_id,
                filename=str(summary.get("name") or "Strava activity")[:255],
                name=activity_name(activity.name),
            )
            _describe(row, activity, described, _settings(session))
            connection = _connected(session)
            session.add(row)
            connection.imported += 1
            advance(connection, phase, activity.start_time)
            session.flush()
            (self.originals / key).write_bytes(original)
            activity.records.write_parquet(self.streams / f"{key}.parquet")
            session.commit()

    def strava_without_laps(self) -> tuple[tuple[int, str], ...]:
        with Session(self.engine) as session:
            missing = session.execute(
                select(ActivityRow.id, ActivityRow.external_id)
                .where(
                    ActivityRow.external_source == STRAVA,
                    ActivityRow.sha256.is_(None),
                    ActivityRow.laps.is_(None),
                    ActivityRow.external_id.is_not(None),
                )
                .order_by(ActivityRow.start_time.desc())
            )
            return tuple((row_id, str(strava_id)) for row_id, strava_id in missing)

    def save_strava_laps(self, row_id: int, listed: Any, laps: tuple[Lap, ...]) -> None:
        with self.writing, Session(self.engine) as session:
            row = session.get(ActivityRow, row_id)
            if row is None or row.laps is not None:
                return
            if listed is not None:
                self._keep_strava_laps(row, listed)
            row.laps = _encode_laps(laps)
            session.commit()

    def _keep_strava_laps(self, row: ActivityRow, listed: Any) -> None:
        path = self.originals / row.storage_key
        try:
            original = json.loads(gzip.decompress(path.read_bytes()))
            original["activity"]["laps"] = listed
            _replace_bytes(gzip.compress(json.dumps(original).encode()), path)
        except (OSError, ValueError) as error:
            log.warning("cannot store the laps of activity %s in its original: %s", row.id, error)

    def skip_strava(
        self, summary: Mapping[str, Any], start: dt.datetime, reason: str, phase: Phase
    ) -> None:
        entry = skipped_entry(
            str(summary["id"]), summary.get("name"), "Strava activity", start, reason
        )
        with self.writing, Session(self.engine) as session:
            record_skip(_connected(session), entry, phase, start)
            session.commit()

    def disconnect_strava(self) -> int:
        with self.writing, Session(self.engine) as session:
            removed = []
            rows = session.scalars(select(ActivityRow).where(ActivityRow.external_source == STRAVA))
            for row in rows:
                if row.sha256 is None:
                    removed.append(row.storage_key)
                    session.delete(row)
                else:
                    row.external_source = None
                    row.external_id = None
            connection = session.get(StravaConnectionRow, CONNECTION_ID)
            if connection is not None:
                session.delete(connection)
            session.commit()
            for key in removed:
                self._remove_files(key)
            return len(removed)

    def _remove_files(self, storage_key: str) -> None:
        (self.originals / storage_key).unlink(missing_ok=True)
        (self.streams / f"{storage_key}.parquet").unlink(missing_ok=True)


def _describe(
    row: ActivityRow, activity: Activity, summary: Summary, settings: AthleteSettings | None
) -> None:
    row.source_format = activity.source_format
    row.sport = activity.sport.value
    row.device = activity.device
    row.start_time = activity.start_time
    row.distance_m = summary.distance_m
    row.elapsed_s = summary.elapsed_s
    row.moving_s = summary.moving_s
    row.pace_s_per_km = summary.pace_s_per_km
    row.avg_heart_rate = summary.avg_heart_rate
    row.max_heart_rate = summary.max_heart_rate
    row.elevation_gain_m = summary.elevation_gain_m
    row.trimp = _trimp(activity, settings) if settings else None
    row.laps = _encode_laps(activity.laps)
    row.best_efforts = stored_efforts(activity)


def _replace_parquet(records: pl.DataFrame, path: Path) -> None:
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        records.write_parquet(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _replace_bytes(data: bytes, path: Path) -> None:
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
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


def _connection(session: Session) -> StravaConnectionRow:
    row = session.get(StravaConnectionRow, CONNECTION_ID)
    if row is None:
        row = StravaConnectionRow(
            id=CONNECTION_ID, backfill_done=False, syncing=False, imported=0, matched=0, skipped=[]
        )
        session.add(row)
    return row


def _connected(session: Session) -> StravaConnectionRow:
    row = session.get(StravaConnectionRow, CONNECTION_ID)
    if row is None or row.access_token is None:
        raise Unauthorized("not connected to Strava")
    return row


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
        body_mass_kg=row.body_mass_kg,
    )


def _trimp(activity: Activity, settings: AthleteSettings) -> float | None:
    heart_rate = activity.records["heart_rate"]
    if heart_rate.is_nan().fill_null(True).all():
        return None
    return trimp(activity, settings.resting_hr, settings.max_hr, settings.coefficients)

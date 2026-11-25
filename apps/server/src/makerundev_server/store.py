import gzip
import hashlib
import json
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from makerundev import Activity, Lap, load
from makerundev.io import unzip
from makerundev.metrics import ZoneModel, summarize
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from makerundev_server.db import (
    STRAVA,
    ActivityRow,
    AthleteSettingsRow,
    GarminConnectionRow,
    StravaConnectionRow,
    activity_name,
)
from makerundev_server.facts import Refreshed, StoredFacts
from makerundev_server.garmin_store import GarminStore
from makerundev_server.listing import ActivityFilter, ActivitySort, conditions, ordering
from makerundev_server.map_source_store import MapSourceStore
from makerundev_server.matching import synced_match
from makerundev_server.performance_store import PerformanceStore
from makerundev_server.settings import AthleteSettings, TrimpCoefficients
from makerundev_server.strava import Tokens
from makerundev_server.sync_state import CONNECTION_ID, SyncStateStore

SETTINGS_ID = 1


@dataclass(frozen=True, slots=True)
class ImportResult:
    activity_id: int
    created: bool


class Store:
    def __init__(self, data_dir: Path, engine: Engine) -> None:
        self.engine = engine
        self.writing = threading.Lock()
        self.facts = StoredFacts(data_dir)
        self.garmin = GarminStore(engine, self.writing)
        self.map_source = MapSourceStore(engine, self.writing)
        self.strava_state = SyncStateStore(
            engine,
            self.writing,
            StravaConnectionRow,
            "Strava activity",
            lambda row: row.access_token is not None,
        )
        self.garmin_state = SyncStateStore(
            engine, self.writing, GarminConnectionRow, "Garmin activity"
        )
        self.performance = PerformanceStore(engine, self.writing)

    def catch_up(self) -> int:
        with self.writing:
            return self.facts.catch_up(self.engine, self.athlete_settings())

    def import_file(
        self,
        filename: str,
        data: bytes,
        name: str | None = None,
        check: Callable[[Session], object] | None = None,
    ) -> ImportResult:
        entry = unzip(data)
        if entry is not None:
            filename, data = entry
        digest = hashlib.sha256(data).hexdigest()
        with self.writing, Session(self.engine) as session:
            if check is not None:
                check(session)
            existing = session.scalar(select(ActivityRow.id).where(ActivityRow.sha256 == digest))
            if existing is not None:
                return ImportResult(existing, created=False)
            activity = load(data)
            basename = Path(filename).name[:255] or "upload"
            distance_m = summarize(activity).distance_m
            synced = synced_match(session, basename, activity.start_time, distance_m)
            replaced = synced.storage_key if synced is not None else None
            row = synced if synced is not None else ActivityRow()
            row.sha256 = digest
            row.storage_key = digest
            row.filename = basename
            row.name = row.name or activity_name(name) or activity_name(activity.name)
            self.facts.write(session, row, activity, data, _settings(session))
            session.commit()
            if replaced is not None:
                self.facts.remove(replaced)
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

    def highest_heart_rate(self) -> float | None:
        with Session(self.engine) as session:
            return session.scalar(select(func.max(ActivityRow.max_heart_rate)))

    def athlete_settings(self) -> AthleteSettings | None:
        with Session(self.engine) as session:
            return _settings(session)

    def save_athlete_settings(self, settings: AthleteSettings) -> Refreshed:
        with self.writing, Session(self.engine) as session:
            previous = _settings(session)
            refreshed = Refreshed(recomputed=0, unreadable=0)
            if previous is None or previous.trimp_inputs() != settings.trimp_inputs():
                refreshed = self.facts.refresh_trimp(session, settings)
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
            return refreshed

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

    def reset_syncs(self) -> None:
        self.strava_state.interrupt()
        self.garmin_state.interrupt()

    def import_strava(
        self,
        summary: Mapping[str, Any],
        streams: Mapping[str, Any],
        activity: Activity,
        check: Callable[[Session], object],
    ) -> ImportResult:
        strava_id = str(summary["id"])
        original = gzip.compress(json.dumps({"activity": summary, "streams": streams}).encode())
        with self.writing, Session(self.engine) as session:
            check(session)
            existing = session.scalar(
                select(ActivityRow.id).where(
                    ActivityRow.external_source == STRAVA, ActivityRow.external_id == strava_id
                )
            )
            if existing is not None:
                return ImportResult(existing, created=False)
            row = ActivityRow(
                storage_key=f"strava-{strava_id}",
                external_source=STRAVA,
                external_id=strava_id,
                filename=str(summary.get("name") or "Strava activity")[:255],
                name=activity_name(activity.name),
            )
            self.facts.write(session, row, activity, original, _settings(session))
            session.commit()
            return ImportResult(row.id, created=True)

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
            self.facts.keep_strava_laps(row, listed, laps)
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
                self.facts.remove(key)
            return len(removed)


def _connection(session: Session) -> StravaConnectionRow:
    row = session.get(StravaConnectionRow, CONNECTION_ID)
    if row is None:
        row = StravaConnectionRow(
            id=CONNECTION_ID, backfill_done=False, syncing=False, imported=0, matched=0, skipped=[]
        )
        session.add(row)
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

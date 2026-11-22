import datetime as dt
import threading
from collections.abc import Mapping
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from makerundev_server import garmin
from makerundev_server.db import GarminConnectionRow
from makerundev_server.matching import nearby, same_activity
from makerundev_server.sync_state import (
    CONNECTION_ID,
    Phase,
    advance,
    begin_sync,
    end_sync,
    record_skip,
    skipped_entry,
)


class GarminStore:
    def __init__(self, engine: Engine, writing: threading.Lock) -> None:
        self.engine = engine
        self.writing = writing

    def connection(self) -> GarminConnectionRow | None:
        with Session(self.engine) as session:
            return session.get(GarminConnectionRow, CONNECTION_ID)

    def save_key(self, key: str, token: garmin.Token) -> None:
        with self.writing, Session(self.engine) as session:
            row = session.get(GarminConnectionRow, CONNECTION_ID)
            if row is None:
                row = GarminConnectionRow(
                    id=CONNECTION_ID,
                    backfill_done=False,
                    syncing=False,
                    imported=0,
                    matched=0,
                    skipped=[],
                )
                session.add(row)
            row.api_key = key
            row.token = token.value
            row.token_expires_at = token.expires_at
            row.sync_message = None
            session.commit()

    def save_token(self, token: garmin.Token) -> None:
        with self.writing, Session(self.engine) as session:
            row = _connected(session)
            row.token = token.value
            row.token_expires_at = token.expires_at
            session.commit()

    def start_sync(self) -> bool:
        with self.writing, Session(self.engine) as session:
            row = session.get(GarminConnectionRow, CONNECTION_ID)
            if row is None or row.syncing:
                return False
            begin_sync(row)
            session.commit()
            return True

    def finish_sync(self, message: str) -> None:
        with self.writing, Session(self.engine) as session:
            row = session.get(GarminConnectionRow, CONNECTION_ID)
            if row is not None:
                end_sync(row, message)
                session.commit()

    def finish_backfill(self) -> None:
        with self.writing, Session(self.engine) as session:
            _connected(session).backfill_done = True
            session.commit()

    def claim(self, start: dt.datetime, distance_m: float, name: str | None, phase: Phase) -> bool:
        with self.writing, Session(self.engine) as session:
            connection = _connected(session)
            match = next(
                (
                    row
                    for row in nearby(session, start)
                    if row.sha256 is not None
                    and same_activity(start, distance_m, row.start_time, row.distance_m)
                ),
                None,
            )
            if match is None:
                return False
            match.name = match.name or name
            connection.matched += 1
            advance(connection, phase, start)
            session.commit()
            return True

    def record_import(self, created: bool, start: dt.datetime, phase: Phase) -> None:
        with self.writing, Session(self.engine) as session:
            connection = _connected(session)
            if created:
                connection.imported += 1
            else:
                connection.matched += 1
            advance(connection, phase, start)
            session.commit()

    def skip(
        self, listed: Mapping[str, Any], start: dt.datetime, reason: str, phase: Phase
    ) -> None:
        entry = skipped_entry(
            str(listed.get("activityId")),
            listed.get("activityName"),
            "Garmin activity",
            start,
            reason,
        )
        with self.writing, Session(self.engine) as session:
            record_skip(_connected(session), entry, phase, start)
            session.commit()

    def remove_key(self) -> None:
        with self.writing, Session(self.engine) as session:
            row = session.get(GarminConnectionRow, CONNECTION_ID)
            if row is not None:
                session.delete(row)
                session.commit()


def _connected(session: Session) -> GarminConnectionRow:
    row = session.get(GarminConnectionRow, CONNECTION_ID)
    if row is None:
        raise garmin.Unauthorized("no Garmin key")
    return row

import datetime as dt
import threading
from collections.abc import Callable
from typing import Literal

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from makerundev_server.db import Outcome, SyncState

CONNECTION_ID = 1
SKIPPED_KEPT = 50

Phase = Literal["newer", "backfill"]
Claim = Literal["known", "matched"]


class Disconnected(Exception):
    pass


class SyncStateStore[Row: SyncState]:
    def __init__(
        self,
        engine: Engine,
        writing: threading.Lock,
        row_type: type[Row],
        unnamed: str,
        connected: Callable[[Row], bool] = lambda row: True,
    ) -> None:
        self.engine = engine
        self.writing = writing
        self.row_type = row_type
        self.unnamed = unnamed
        self.connected = connected

    def connection(self) -> Row | None:
        with Session(self.engine) as session:
            row = session.get(self.row_type, CONNECTION_ID)
            return row if row is not None and self.connected(row) else None

    def ensure(self, session: Session) -> Row:
        row = session.get(self.row_type, CONNECTION_ID)
        if row is None or not self.connected(row):
            raise Disconnected
        return row

    def start(self) -> bool:
        with self.writing, Session(self.engine) as session:
            row = session.get(self.row_type, CONNECTION_ID)
            if row is None or not self.connected(row) or row.syncing:
                return False
            row.syncing = True
            row.sync_outcome = None
            row.resume_at = None
            row.imported = 0
            row.matched = 0
            session.commit()
            return True

    def finish(self, outcome: Outcome, resume_at: dt.datetime | None = None) -> None:
        with self.writing, Session(self.engine) as session:
            row = session.get(self.row_type, CONNECTION_ID)
            if row is not None:
                row.syncing = False
                row.sync_outcome = outcome
                row.resume_at = resume_at
                row.last_sync_at = dt.datetime.now(dt.UTC)
                session.commit()

    def interrupt(self) -> None:
        with self.writing, Session(self.engine) as session:
            row = session.get(self.row_type, CONNECTION_ID)
            if row is not None and row.syncing:
                row.syncing = False
                row.sync_outcome = "interrupted"
                row.resume_at = None
                session.commit()

    def finish_backfill(self) -> None:
        with self.writing, Session(self.engine) as session:
            self.ensure(session).backfill_done = True
            session.commit()

    def claim(
        self, start: dt.datetime, phase: Phase, match: Callable[[Session], Claim | None]
    ) -> bool:
        with self.writing, Session(self.engine) as session:
            connection = self.ensure(session)
            claimed = match(session)
            if claimed is None:
                return False
            if claimed == "matched":
                connection.matched += 1
            _advance(connection, phase, start)
            session.commit()
            return True

    def record_import(self, created: bool, start: dt.datetime, phase: Phase) -> None:
        with self.writing, Session(self.engine) as session:
            connection = self.ensure(session)
            if created:
                connection.imported += 1
            else:
                connection.matched += 1
            _advance(connection, phase, start)
            session.commit()

    def skip(
        self, source_id: str, name: str | None, start: dt.datetime, reason: str, phase: Phase
    ) -> None:
        entry = {
            "id": source_id,
            "name": (name or self.unnamed)[:255],
            "start_time": start.isoformat(),
            "reason": reason[:255],
        }
        with self.writing, Session(self.engine) as session:
            connection = self.ensure(session)
            earlier = [item for item in connection.skipped if item.get("id") != source_id]
            connection.skipped = [entry, *earlier][:SKIPPED_KEPT]
            _advance(connection, phase, start)
            session.commit()


def _advance(connection: SyncState, phase: Phase, start: dt.datetime) -> None:
    if phase == "backfill":
        connection.backfill_before = start
    if connection.newest_synced is None or start > connection.newest_synced:
        connection.newest_synced = start


def utc(text: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)

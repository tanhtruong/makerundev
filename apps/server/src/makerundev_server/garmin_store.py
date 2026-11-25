import threading

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from makerundev_server import garmin
from makerundev_server.db import GarminConnectionRow
from makerundev_server.sync_state import CONNECTION_ID, Disconnected


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
            row.sync_outcome = None
            row.resume_at = None
            session.commit()

    def save_token(self, token: garmin.Token) -> None:
        with self.writing, Session(self.engine) as session:
            row = session.get(GarminConnectionRow, CONNECTION_ID)
            if row is None:
                raise Disconnected
            row.token = token.value
            row.token_expires_at = token.expires_at
            session.commit()

    def remove_key(self) -> None:
        with self.writing, Session(self.engine) as session:
            row = session.get(GarminConnectionRow, CONNECTION_ID)
            if row is not None:
                session.delete(row)
                session.commit()

import datetime as dt
import threading
from collections.abc import Callable

from fastapi import FastAPI
from pydantic import BaseModel

from makerundev_server.db import Outcome, SyncState
from makerundev_server.sync_state import utc


class SkippedActivity(BaseModel):
    id: str
    name: str
    start_time: dt.datetime
    reason: str
    url: str


class SyncStatus(BaseModel):
    syncing: bool
    last_sync_at: dt.datetime | None
    imported: int
    matched: int
    backfill_done: bool
    backfill_before: dt.datetime | None
    outcome: Outcome | None
    resume_at: dt.datetime | None
    skipped: list[SkippedActivity]


def run_in_background(
    app: FastAPI, name: str, start: Callable[[], bool], run: Callable[[], None]
) -> None:
    running = getattr(app.state, name, None)
    if running is not None and running.is_alive():
        return
    if start():
        worker = threading.Thread(target=run, daemon=True)
        setattr(app.state, name, worker)
        worker.start()


def sync_status(row: SyncState, activity_url: str) -> SyncStatus:
    return SyncStatus(
        syncing=row.syncing,
        last_sync_at=row.last_sync_at,
        imported=row.imported,
        matched=row.matched,
        backfill_done=row.backfill_done,
        backfill_before=row.backfill_before,
        outcome=row.sync_outcome,
        resume_at=row.resume_at,
        skipped=[
            SkippedActivity(
                id=item["id"],
                name=item["name"],
                start_time=utc(item["start_time"]),
                reason=item["reason"],
                url=activity_url.format(item["id"]),
            )
            for item in row.skipped
        ],
    )

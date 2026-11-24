import datetime as dt
from typing import Any, Literal

from makerundev_server.db import Outcome, SyncState

CONNECTION_ID = 1
SKIPPED_KEPT = 50
REFRESH_MARGIN = dt.timedelta(hours=1)

Phase = Literal["newer", "backfill"]


def begin_sync(row: SyncState) -> None:
    row.syncing = True
    row.sync_outcome = None
    row.resume_at = None
    row.imported = 0
    row.matched = 0


def end_sync(row: SyncState, outcome: Outcome, resume_at: dt.datetime | None = None) -> None:
    row.syncing = False
    row.sync_outcome = outcome
    row.resume_at = resume_at
    row.last_sync_at = dt.datetime.now(dt.UTC)


def skipped_entry(
    source_id: str, name: Any, fallback_name: str, start: dt.datetime, reason: str
) -> dict[str, str]:
    return {
        "id": source_id,
        "name": str(name or fallback_name)[:255],
        "start_time": start.isoformat(),
        "reason": reason[:255],
    }


def record_skip(row: SyncState, entry: dict[str, str], phase: Phase, start: dt.datetime) -> None:
    earlier = [item for item in row.skipped if item.get("id") != entry["id"]]
    row.skipped = [entry, *earlier][:SKIPPED_KEPT]
    advance(row, phase, start)


def advance(connection: SyncState, phase: Phase, start: dt.datetime) -> None:
    if phase == "backfill":
        connection.backfill_before = start
    if connection.newest_synced is None or start > connection.newest_synced:
        connection.newest_synced = start


def utc(text: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)

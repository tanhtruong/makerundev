import datetime as dt
import logging
from collections.abc import Iterator
from pathlib import PurePosixPath
from typing import Any

from makerundev import ActivityFileError
from makerundev.io import unzip
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from makerundev_server import garmin
from makerundev_server.db import GarminConnectionRow, activity_name
from makerundev_server.matching import nearby, same_activity, strava_id_in
from makerundev_server.store import Store
from makerundev_server.sync_run import Listed, Skipped, SyncRun, Token
from makerundev_server.sync_state import Claim, Disconnected, utc

UNREADABLE = "the file could not be imported; see the server log"
MANUAL = "a manual entry, with no file"
NOT_A_ZIP = "Garmin did not send a ZIP"
DATE_MARGIN = dt.timedelta(days=1)

log = logging.getLogger(__name__)


class GarminProvider:
    name = "Garmin"

    def __init__(self, store: Store, client: garmin.GarminClient) -> None:
        self.store = store
        self.client = client
        self.state = store.garmin_state

    def held(self, row: GarminConnectionRow) -> tuple[str | None, dt.datetime | None]:
        return row.token, row.token_expires_at

    def renew(self, row: GarminConnectionRow) -> str:
        token = self.client.token(row.api_key)
        self.store.garmin.save_token(token)
        return token.value

    def listed(
        self, newer_than: dt.datetime | None, older_than: dt.datetime | None, token: Token
    ) -> Iterator[list[Listed]]:
        since = (newer_than - DATE_MARGIN).date() if newer_than is not None else None
        handled: set[str] = set()
        offset = 0
        while True:
            until = (older_than + DATE_MARGIN).date() if older_than is not None else None
            page = self.client.activities(token(), offset, since=since, until=until)
            batch = sorted(
                (
                    item
                    for item in _listed(page)
                    if item.source_id not in handled
                    and (newer_than is None or item.start > newer_than)
                    and (older_than is None or item.start <= older_than)
                ),
                key=lambda item: item.start,
                reverse=True,
            )
            if batch:
                yield batch
                handled.update(item.source_id for item in batch)
                older_than = batch[-1].start
                offset = 0
            else:
                offset += garmin.PAGE_SIZE
            if len(page) < garmin.PAGE_SIZE:
                return

    def claim(self, session: Session, item: Listed) -> Claim | None:
        match = next(
            (
                row
                for row in nearby(session, item.start)
                if row.sha256 is not None
                and same_activity(item.start, item.distance_m, row.start_time, row.distance_m)
            ),
            None,
        )
        if match is None:
            return None
        match.name = match.name or item.name
        return "matched"

    def bring_in(self, item: Listed, token: Token) -> bool:
        if item.manual:
            raise Skipped(MANUAL)
        name, body = _garmin_file(item.source_id, self.client.download(token(), item.source_id))
        try:
            return self.store.import_file(name, body, item.name, self.state.ensure).created
        except (ActivityFileError, Disconnected, OSError, SQLAlchemyError):
            raise
        except Exception as error:
            log.exception("Garmin activity %s could not be imported", item.source_id)
            raise Skipped(UNREADABLE) from error

    def finish(self, token: Token) -> None:
        return None


def garmin_sync(store: Store, client: garmin.GarminClient) -> SyncRun[GarminConnectionRow]:
    return SyncRun(GarminProvider(store, client))


def _listed(page: list[dict[str, Any]]) -> list[Listed]:
    listed = []
    for entry in page:
        try:
            listed.append(
                Listed(
                    source_id=str(entry["activityId"]),
                    start=utc(str(entry["startTimeGMT"])),
                    name=activity_name(entry.get("activityName")),
                    distance_m=float(entry.get("distance") or 0.0),
                    manual=bool(entry.get("manualActivity") or entry.get("isManualActivity")),
                    entry=entry,
                )
            )
        except (KeyError, TypeError, ValueError):
            log.warning("Garmin activity %s has no readable start time", entry.get("activityId"))
    return listed


def _garmin_file(activity_id: str, data: bytes) -> tuple[str, bytes]:
    entry = unzip(data)
    if entry is None:
        raise ActivityFileError(NOT_A_ZIP)
    if strava_id_in(entry.name) is not None:
        return f"garmin-{activity_id}{PurePosixPath(entry.name).suffix}", entry.data
    return entry.name, entry.data

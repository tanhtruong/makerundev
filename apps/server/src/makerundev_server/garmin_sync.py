import datetime as dt
import logging
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import httpx2
from makerundev import ActivityFileError
from makerundev.io import unzip
from sqlalchemy.exc import SQLAlchemyError

from makerundev_server import garmin
from makerundev_server.matching import strava_id_in
from makerundev_server.store import Store
from makerundev_server.sync_state import FAILED, REFRESH_MARGIN, UP_TO_DATE, Phase, utc

PAUSED = "Garmin asked to slow down. Sync again later."
EXPIRED = (
    "Garmin no longer accepts this key: it has expired or was revoked."
    " Create a new one in Garmin Connect under Settings, Personal API Key, and save it below."
)
UNREACHABLE = "Garmin could not be reached. Sync again later."
UNREADABLE = "the file could not be imported; see the server log"
MANUAL = "a manual entry, with no file"
NOT_A_ZIP = "Garmin did not send a ZIP"
DATE_MARGIN = dt.timedelta(days=1)

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GarminListing:
    entry: Mapping[str, Any]
    activity_id: str
    start: dt.datetime
    distance_m: float
    manual: bool


class GarminSync:
    def __init__(self, store: Store, client: garmin.GarminClient) -> None:
        self.store = store
        self.client = client

    def run(self) -> None:
        message = FAILED
        try:
            self._newer()
            self._backfill()
            message = UP_TO_DATE
        except garmin.RateLimited as limit:
            message = _paused(limit.retry_after)
        except garmin.Unauthorized:
            message = EXPIRED
        except (httpx2.HTTPError, garmin.GarminError) as error:
            log.warning("Garmin sync stopped: %s", type(error).__name__)
            message = UNREACHABLE
        except Exception:
            log.exception("Garmin sync failed")
        finally:
            self.store.garmin.finish_sync(message)

    def access_token(self) -> str:
        row = self.store.garmin.connection()
        if row is None:
            raise garmin.Unauthorized("no Garmin key")
        expires_at = row.token_expires_at or dt.datetime.now(dt.UTC)
        if row.token and expires_at - dt.datetime.now(dt.UTC) > REFRESH_MARGIN:
            return row.token
        token = self.client.token(row.api_key)
        self.store.garmin.save_token(token)
        return token.value

    def _newer(self) -> None:
        row = self.store.garmin.connection()
        if row is None or row.newest_synced is None:
            return
        found = [item for batch in self._walk(row.newest_synced, None) for item in batch]
        for item in sorted(found, key=lambda item: item.start):
            self._one(item, "newer")

    def _backfill(self) -> None:
        row = self.store.garmin.connection()
        if row is None or row.backfill_done:
            return
        for batch in self._walk(None, row.backfill_before):
            for item in batch:
                self._one(item, "backfill")
        self.store.garmin.finish_backfill()

    def _walk(
        self, newer_than: dt.datetime | None, low: dt.datetime | None
    ) -> Iterator[list[GarminListing]]:
        since = (newer_than - DATE_MARGIN).date() if newer_than is not None else None
        handled: set[str] = set()
        offset = 0
        while True:
            until = (low + DATE_MARGIN).date() if low is not None else None
            page = self.client.activities(self.access_token(), offset, since=since, until=until)
            batch = sorted(
                (
                    item
                    for item in _listings(page)
                    if item.activity_id not in handled
                    and (newer_than is None or item.start > newer_than)
                    and (low is None or item.start <= low)
                ),
                key=lambda item: item.start,
                reverse=True,
            )
            if batch:
                yield batch
                handled.update(item.activity_id for item in batch)
                low = batch[-1].start
                offset = 0
            else:
                offset += garmin.PAGE_SIZE
            if len(page) < garmin.PAGE_SIZE:
                return

    def _one(self, item: GarminListing, phase: Phase) -> None:
        if self.store.garmin.claim(item.start, item.distance_m, phase):
            return
        if item.manual:
            self.store.garmin.skip(item.entry, item.start, MANUAL, phase)
            return
        try:
            data = self.client.download(self.access_token(), item.activity_id)
            name, body = _garmin_file(item.activity_id, data)
        except (garmin.Refused, ActivityFileError) as error:
            self.store.garmin.skip(item.entry, item.start, str(error), phase)
            return
        if self.store.garmin.connection() is None:
            raise garmin.Unauthorized("no Garmin key")
        try:
            result = self.store.import_file(name, body)
        except ActivityFileError as error:
            self.store.garmin.skip(item.entry, item.start, str(error), phase)
            return
        except (OSError, SQLAlchemyError):
            raise
        except Exception:
            log.exception("Garmin activity %s could not be imported", item.activity_id)
            self.store.garmin.skip(item.entry, item.start, UNREADABLE, phase)
            return
        self.store.garmin.record_import(result.created, item.start, phase)


def _listings(page: list[dict[str, Any]]) -> list[GarminListing]:
    listings = []
    for entry in page:
        try:
            listings.append(
                GarminListing(
                    entry=entry,
                    activity_id=str(entry["activityId"]),
                    start=utc(str(entry["startTimeGMT"])),
                    distance_m=float(entry.get("distance") or 0.0),
                    manual=bool(entry.get("manualActivity") or entry.get("isManualActivity")),
                )
            )
        except (KeyError, TypeError, ValueError):
            log.warning("Garmin activity %s has no readable start time", entry.get("activityId"))
    return listings


def _garmin_file(activity_id: str, data: bytes) -> tuple[str, bytes]:
    entry = unzip(data)
    if entry is None:
        raise ActivityFileError(NOT_A_ZIP)
    if strava_id_in(entry.name) is not None:
        return f"garmin-{activity_id}{PurePosixPath(entry.name).suffix}", entry.data
    return entry.name, entry.data


def _paused(retry_after: str | None) -> str:
    minutes = garmin.retry_minutes(retry_after, dt.datetime.now(dt.UTC))
    if minutes is None:
        return PAUSED
    unit = "minute" if minutes == 1 else "minutes"
    return f"Garmin asked to slow down. Sync again in {minutes} {unit}."

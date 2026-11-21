import datetime as dt
import logging
from collections.abc import Mapping
from typing import Any

import httpx2
from makerundev import ActivityFileError
from makerundev.io.strava import read_strava

from makerundev_server.store import Store
from makerundev_server.strava import (
    RateLimited,
    Refused,
    StravaClient,
    StravaError,
    Unauthorized,
)
from makerundev_server.sync_state import FAILED, REFRESH_MARGIN, UP_TO_DATE, Phase, utc

PAUSED_SHORT = "Paused at Strava's 15-minute rate limit. Sync again in a quarter of an hour."
PAUSED_DAILY = "Paused at Strava's daily rate limit. Sync again after midnight UTC."
REJECTED = "Strava no longer accepts this connection. Disconnect and connect again."
UNREACHABLE = "Strava could not be reached. Sync again later."

log = logging.getLogger(__name__)


class StravaSync:
    def __init__(self, store: Store, client: StravaClient) -> None:
        self.store = store
        self.client = client

    def run(self) -> None:
        message = FAILED
        try:
            self._newer()
            self._backfill()
            message = UP_TO_DATE
        except RateLimited as limit:
            message = PAUSED_DAILY if limit.daily else PAUSED_SHORT
        except Unauthorized:
            message = REJECTED
        except (httpx2.HTTPError, StravaError) as error:
            log.warning("Strava sync stopped: %s", type(error).__name__)
            message = UNREACHABLE
        except Exception:
            log.exception("Strava sync failed")
        finally:
            self.store.finish_strava_sync(message)

    def access_token(self) -> str:
        row = self.store.strava_connection()
        if row is None or row.access_token is None or row.refresh_token is None:
            raise Unauthorized("not connected to Strava")
        expires_at = row.expires_at or dt.datetime.now(dt.UTC)
        if expires_at - dt.datetime.now(dt.UTC) > REFRESH_MARGIN:
            return row.access_token
        tokens = self.client.refresh(row.refresh_token)
        self.store.save_strava_tokens(tokens)
        return tokens.access_token

    def _newer(self) -> None:
        row = self.store.strava_connection()
        if row is None or row.newest_synced is None:
            return
        listed: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self.client.activities(self.access_token(), after=row.newest_synced, page=page)
            listed.extend(batch)
            if not batch:
                break
            page += 1
        for start, summary in sorted(_dated(listed), key=lambda dated: dated[0]):
            self._one(summary, start, "newer")

    def _backfill(self) -> None:
        while True:
            row = self.store.strava_connection()
            if row is None or row.backfill_done:
                return
            before = row.backfill_before
            batch = self.client.activities(self.access_token(), before=before)
            for start, summary in sorted(_dated(batch), key=lambda dated: dated[0], reverse=True):
                self._one(summary, start, "backfill")
            after = self.store.strava_connection()
            if not batch or after is None or after.backfill_before == before:
                self.store.finish_strava_backfill()
                return

    def _one(self, summary: Mapping[str, Any], start: dt.datetime, phase: Phase) -> None:
        if self.store.claim_strava(summary, start, phase):
            return
        if summary.get("manual"):
            self.store.skip_strava(summary, start, "a manual entry, with no streams", phase)
            return
        try:
            streams = self.client.streams(self.access_token(), str(summary["id"]))
        except Refused as refused:
            self.store.skip_strava(summary, start, str(refused), phase)
            return
        if streams is None:
            self.store.skip_strava(summary, start, "no streams on Strava", phase)
            return
        try:
            activity = read_strava(summary, streams)
        except ActivityFileError as error:
            self.store.skip_strava(summary, start, str(error), phase)
            return
        self.store.add_strava(summary, streams, activity, phase)


def _dated(listed: list[dict[str, Any]]) -> list[tuple[dt.datetime, dict[str, Any]]]:
    dated = []
    for summary in listed:
        try:
            dated.append((_start(summary), summary))
        except (KeyError, ValueError):
            log.warning("Strava activity %s has no readable start time", summary.get("id"))
    return dated


def _start(summary: Mapping[str, Any]) -> dt.datetime:
    return utc(str(summary["start_date"]))

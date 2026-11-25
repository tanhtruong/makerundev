import datetime as dt
import logging
from collections.abc import Mapping
from typing import Any

import httpx2
from makerundev import ActivityFileError
from makerundev.io.strava import read_strava, strava_laps

from makerundev_server.db import Outcome
from makerundev_server.store import Store
from makerundev_server.strava import (
    RateLimited,
    Refused,
    StravaClient,
    StravaError,
    Unauthorized,
)
from makerundev_server.sync_state import REFRESH_MARGIN, Phase, utc

log = logging.getLogger(__name__)


class StravaSync:
    def __init__(self, store: Store, client: StravaClient) -> None:
        self.store = store
        self.client = client

    def run(self) -> None:
        outcome: Outcome = "failed"
        try:
            self._newer()
            self._backfill()
            self._laps()
            outcome = "up_to_date"
        except RateLimited as limit:
            outcome = "paused_daily" if limit.daily else "paused_short"
        except Unauthorized:
            outcome = "rejected"
        except (httpx2.HTTPError, StravaError) as error:
            log.warning("Strava sync stopped: %s", type(error).__name__)
            outcome = "unreachable"
        except Exception:
            log.exception("Strava sync failed")
        finally:
            self.store.finish_strava_sync(outcome)

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
        self.client.ensure(2)
        try:
            streams = self.client.streams(self.access_token(), str(summary["id"]))
        except Refused as refused:
            self.store.skip_strava(summary, start, str(refused), phase)
            return
        if streams is None:
            self.store.skip_strava(summary, start, "no streams on Strava", phase)
            return
        detail = self._detail(str(summary["id"]))
        kept = dict(summary) if detail is None else {**summary, "laps": detail.get("laps")}
        try:
            activity = read_strava(kept, streams)
        except ActivityFileError as error:
            self.store.skip_strava(summary, start, str(error), phase)
            return
        self.store.import_strava(kept, streams, activity)
        self.store.record_strava_import(start, phase)

    def _laps(self) -> None:
        for row_id, strava_id in self.store.strava_without_laps():
            detail = self._detail(strava_id)
            if detail is None:
                self.store.save_strava_laps(row_id, None, ())
            else:
                listed = detail.get("laps")
                self.store.save_strava_laps(row_id, listed, strava_laps(detail))

    def _detail(self, strava_id: str) -> dict[str, Any] | None:
        try:
            return self.client.activity(self.access_token(), strava_id)
        except Refused:
            return None


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

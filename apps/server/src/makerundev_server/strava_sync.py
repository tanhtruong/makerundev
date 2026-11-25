import datetime as dt
import logging
from collections.abc import Iterator, Mapping
from typing import Any

from makerundev.io.strava import read_strava, strava_laps
from sqlalchemy import select
from sqlalchemy.orm import Session

from makerundev_server.db import STRAVA, ActivityRow, StravaConnectionRow, activity_name
from makerundev_server.matching import file_match
from makerundev_server.store import Store
from makerundev_server.strava import StravaClient
from makerundev_server.sync_errors import Refused, Unauthorized
from makerundev_server.sync_run import Listed, Skipped, SyncRun, Token
from makerundev_server.sync_state import Claim, utc

log = logging.getLogger(__name__)


class StravaProvider:
    name = "Strava"

    def __init__(self, store: Store, client: StravaClient) -> None:
        self.store = store
        self.client = client
        self.state = store.strava_state

    def held(self, row: StravaConnectionRow) -> tuple[str | None, dt.datetime | None]:
        return row.access_token, row.expires_at

    def renew(self, row: StravaConnectionRow) -> str:
        if row.refresh_token is None:
            raise Unauthorized("not connected to Strava")
        tokens = self.client.refresh(row.refresh_token)
        self.store.save_strava_tokens(tokens)
        return tokens.access_token

    def listed(
        self, newer_than: dt.datetime | None, older_than: dt.datetime | None, token: Token
    ) -> Iterator[list[Listed]]:
        if newer_than is not None:
            found: list[Listed] = []
            page = 1
            while batch := self.client.activities(token(), after=newer_than, page=page):
                found.extend(_listed(batch))
                page += 1
            yield found
            return
        while True:
            dated = sorted(
                _listed(self.client.activities(token(), before=older_than)),
                key=lambda item: item.start,
                reverse=True,
            )
            if not dated:
                return
            yield dated
            older_than = dated[-1].start

    def claim(self, session: Session, item: Listed) -> Claim | None:
        known = session.scalar(
            select(ActivityRow.id).where(
                ActivityRow.external_source == STRAVA, ActivityRow.external_id == item.source_id
            )
        )
        if known is not None:
            return "known"
        file_row = file_match(session, item.source_id, item.start, item.distance_m)
        if file_row is None:
            return None
        file_row.external_source = STRAVA
        file_row.external_id = item.source_id
        file_row.name = item.name or file_row.name
        return "matched"

    def bring_in(self, item: Listed, token: Token) -> bool:
        if item.manual:
            raise Skipped("a manual entry, with no streams")
        self.client.ensure(2)
        streams = self.client.streams(token(), item.source_id)
        if streams is None:
            raise Skipped("no streams on Strava")
        detail = self._detail(item.source_id, token)
        summary = dict(item.entry)
        kept = summary if detail is None else {**summary, "laps": detail.get("laps")}
        activity = read_strava(kept, streams)
        return self.store.import_strava(kept, streams, activity, self.state.ensure).created

    def finish(self, token: Token) -> None:
        for row_id, strava_id in self.store.strava_without_laps():
            detail = self._detail(strava_id, token)
            if detail is None:
                self.store.save_strava_laps(row_id, None, ())
            else:
                self.store.save_strava_laps(row_id, detail.get("laps"), strava_laps(detail))

    def _detail(self, strava_id: str, token: Token) -> dict[str, Any] | None:
        try:
            return self.client.activity(token(), strava_id)
        except Refused:
            return None


def strava_sync(store: Store, client: StravaClient) -> SyncRun[StravaConnectionRow]:
    return SyncRun(StravaProvider(store, client))


def _listed(page: list[dict[str, Any]]) -> list[Listed]:
    listed = []
    for summary in page:
        try:
            listed.append(_listing(summary))
        except (KeyError, TypeError, ValueError):
            log.warning("Strava activity %s has no readable start time", summary.get("id"))
    return listed


def _listing(summary: Mapping[str, Any]) -> Listed:
    return Listed(
        source_id=str(summary["id"]),
        start=utc(str(summary["start_date"])),
        name=activity_name(summary.get("name")),
        distance_m=float(summary.get("distance") or 0.0),
        manual=bool(summary.get("manual")),
        entry=summary,
    )

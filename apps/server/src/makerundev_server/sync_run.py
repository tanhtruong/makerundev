import datetime as dt
import logging
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import httpx2
from makerundev import ActivityFileError
from sqlalchemy.orm import Session

from makerundev_server.db import Outcome, SyncState
from makerundev_server.sync_errors import RateLimited, Refused, SyncError, Unauthorized
from makerundev_server.sync_state import Claim, Disconnected, Phase, SyncStateStore

REFRESH_MARGIN = dt.timedelta(hours=1)

Token = Callable[[], str]

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Listed:
    source_id: str
    start: dt.datetime
    name: str | None
    distance_m: float
    manual: bool
    entry: Mapping[str, Any]


class Skipped(Exception):
    pass


class Provider[Row: SyncState](Protocol):
    name: str
    state: SyncStateStore[Row]

    def held(self, row: Row) -> tuple[str | None, dt.datetime | None]: ...

    def renew(self, row: Row) -> str: ...

    def listed(
        self, newer_than: dt.datetime | None, older_than: dt.datetime | None, token: Token
    ) -> Iterator[list[Listed]]: ...

    def claim(self, session: Session, item: Listed) -> Claim | None: ...

    def bring_in(self, item: Listed, token: Token) -> bool: ...

    def finish(self, token: Token) -> None: ...


class SyncRun[Row: SyncState]:
    def __init__(self, provider: Provider[Row]) -> None:
        self.provider = provider
        self.state = provider.state

    def run(self) -> None:
        outcome: Outcome = "failed"
        resume_at = None
        try:
            self._newer()
            self._backfill()
            self.provider.finish(self.access_token)
            outcome = "up_to_date"
        except RateLimited as limit:
            outcome = limit.outcome
            resume_at = limit.resume_at
        except (Unauthorized, Disconnected):
            outcome = "rejected"
        except (httpx2.HTTPError, SyncError) as error:
            log.warning("%s sync stopped: %s", self.provider.name, type(error).__name__)
            outcome = "unreachable"
        except Exception:
            log.exception("%s sync failed", self.provider.name)
        finally:
            self.state.finish(outcome, resume_at)

    def access_token(self) -> str:
        row = self.state.connection()
        if row is None:
            raise Disconnected
        value, expires_at = self.provider.held(row)
        now = dt.datetime.now(dt.UTC)
        if value and expires_at is not None and expires_at - now > REFRESH_MARGIN:
            return value
        return self.provider.renew(row)

    def _newer(self) -> None:
        row = self.state.connection()
        if row is None or row.newest_synced is None:
            return
        listed = self.provider.listed(row.newest_synced, None, self.access_token)
        found = [item for batch in listed for item in batch]
        for item in sorted(found, key=lambda item: item.start):
            self._one(item, "newer")

    def _backfill(self) -> None:
        row = self.state.connection()
        if row is None or row.backfill_done:
            return
        for batch in self.provider.listed(None, row.backfill_before, self.access_token):
            for item in batch:
                self._one(item, "backfill")
        self.state.finish_backfill()

    def _one(self, item: Listed, phase: Phase) -> None:
        if self.state.claim(item.start, phase, lambda session: self.provider.claim(session, item)):
            return
        try:
            created = self.provider.bring_in(item, self.access_token)
        except (Skipped, Refused, ActivityFileError) as reason:
            self.state.skip(item.source_id, item.name, item.start, str(reason), phase)
            return
        self.state.record_import(created, item.start, phase)

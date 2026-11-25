import datetime as dt
from typing import Literal

Paused = Literal["paused_short", "paused_daily", "paused"]


class SyncError(Exception):
    pass


class RateLimited(SyncError):
    def __init__(self, outcome: Paused, resume_at: dt.datetime | None = None) -> None:
        super().__init__(outcome)
        self.outcome: Paused = outcome
        self.resume_at = resume_at


class Unauthorized(SyncError):
    pass


class Refused(SyncError):
    pass

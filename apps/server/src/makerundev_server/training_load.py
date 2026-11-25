import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from makerundev_server.db import ActivityRow
from makerundev_server.performance import Performance, current_performance
from makerundev_server.store import Store
from makerundev_server.training import LoadActivity, LoadView, load_view

Clock = Callable[[], dt.datetime]

COLUMNS = (
    ActivityRow.id,
    ActivityRow.name,
    ActivityRow.filename,
    ActivityRow.start_time,
    ActivityRow.sport,
    ActivityRow.trimp,
    ActivityRow.excluded_from_performance,
    ActivityRow.best_efforts,
)


def system_clock() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@dataclass(frozen=True, slots=True)
class Reading:
    settings_set: bool
    load: LoadView | None
    performance: Performance | None


class TrainingLoad:
    def __init__(self, store: Store, clock: Clock) -> None:
        self.store = store
        self.clock = clock

    def read(self, days: int | None) -> Reading:
        settings = self.store.athlete_settings()
        timezone = settings.timezone if settings else "UTC"
        today = self.clock().astimezone(ZoneInfo(timezone)).date()
        activities = self._activities()
        return Reading(
            settings_set=settings is not None,
            load=load_view(activities, timezone, today, days) if settings else None,
            performance=current_performance(activities, timezone, today),
        )

    def _activities(self) -> list[LoadActivity]:
        query = select(*COLUMNS).order_by(ActivityRow.start_time.desc())
        with Session(self.store.engine) as session:
            return [
                LoadActivity(
                    id=row.id,
                    name=row.name or row.filename,
                    start_time=row.start_time,
                    sport=row.sport,
                    trimp=row.trimp,
                    excluded_from_performance=row.excluded_from_performance,
                    efforts=[
                        (effort["distance_m"], effort["elapsed_s"])
                        for effort in row.best_efforts or []
                    ],
                )
                for row in session.execute(query)
            ]

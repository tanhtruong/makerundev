import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from makerundev import Sport
from makerundev.metrics import (
    CRITICAL_SPEED_WINDOW_S,
    FITNESS_DAYS,
    CriticalSpeed,
    critical_speed,
    vdot,
)

from makerundev_server.db import ActivityRow
from makerundev_server.performance_store import effort_times
from makerundev_server.training import local_date

COUNTED_SPORTS = frozenset({Sport.RUNNING.value, Sport.TRAIL_RUNNING.value})


@dataclass(frozen=True, slots=True)
class Effort:
    activity_id: int
    activity_name: str
    start_time: dt.datetime
    date: dt.date
    distance_m: float
    elapsed_s: float

    @property
    def day(self) -> str:
        return f"{self.date.day} {self.date:%b}"


@dataclass(frozen=True, slots=True)
class Performance:
    vdot: float | None
    vdot_source: Effort | None
    critical_speed: CriticalSpeed | None
    fitted: list[Effort]
    excluded: int

    @property
    def too_few_efforts(self) -> bool:
        return len({effort.elapsed_s for effort in self.fitted}) < 2


def _recent_runs(rows: Iterable[ActivityRow], timezone: str, today: dt.date) -> list[ActivityRow]:
    first = today - dt.timedelta(days=FITNESS_DAYS - 1)
    return [
        row
        for row in rows
        if row.sport in COUNTED_SPORTS and first <= local_date(row.start_time, timezone) <= today
    ]


def current_performance(
    rows: Sequence[ActivityRow],
    timezone: str,
    today: dt.date,
) -> Performance | None:
    if not rows:
        return None
    recent = _recent_runs(rows, timezone, today)
    counted = [row for row in recent if not row.excluded_from_performance]
    efforts = [
        Effort(
            activity_id=row.id,
            activity_name=row.name or row.filename,
            start_time=row.start_time,
            date=local_date(row.start_time, timezone),
            distance_m=distance_m,
            elapsed_s=elapsed_s,
        )
        for row in counted
        for distance_m, elapsed_s in effort_times(row)
    ]
    scored = [
        (score, effort)
        for effort in efforts
        if (score := vdot(effort.distance_m, effort.elapsed_s)) is not None
    ]
    best = max(scored, key=lambda pair: (pair[0], pair[1].start_time), default=None)
    fastest: dict[float, Effort] = {}
    for effort in efforts:
        known = fastest.get(effort.distance_m)
        if known is None or effort.elapsed_s < known.elapsed_s:
            fastest[effort.distance_m] = effort
    shortest, longest = CRITICAL_SPEED_WINDOW_S
    fitted = sorted(
        (effort for effort in fastest.values() if shortest <= effort.elapsed_s <= longest),
        key=lambda effort: effort.distance_m,
    )
    return Performance(
        vdot=best[0] if best else None,
        vdot_source=best[1] if best else None,
        critical_speed=critical_speed({e.distance_m: e.elapsed_s for e in fitted}),
        fitted=fitted,
        excluded=sum(row.excluded_from_performance for row in recent),
    )

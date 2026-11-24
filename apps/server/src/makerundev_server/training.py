import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal
from zoneinfo import ZoneInfo

from makerundev.metrics import training_load

from makerundev_server.db import ActivityRow

RANGES: dict[str, int | None] = {"90": 90, "180": 180, "365": 365, "all": None}
Range = Literal["90", "180", "365", "all"]

DEFAULT_RANGE: Range = "180"
MIN_LOAD_TOP = 10.0
MIN_FORM_SPAN = 5.0


@dataclass(frozen=True, slots=True)
class Day:
    date: dt.date
    load: float
    fitness: float
    fatigue: float
    form: float


@dataclass(frozen=True, slots=True)
class LoadView:
    days: list[Day]
    activities: int
    without_heart_rate: int

    @property
    def today(self) -> Day:
        return self.days[-1]

    @property
    def weeks(self) -> list[tuple[Day, float]]:
        newest_first = self.days[::-1]
        return [
            (newest_first[start], sum(day.load for day in newest_first[start : start + 7]))
            for start in range(0, len(newest_first), 7)
        ]


@dataclass(frozen=True, slots=True)
class LoadRanges:
    load_top: float
    form_low: float
    form_high: float


def load_ranges(days: Sequence[Day]) -> LoadRanges:
    return LoadRanges(
        load_top=max(MIN_LOAD_TOP, *(max(day.fitness, day.fatigue) for day in days)),
        form_low=min(-MIN_FORM_SPAN, *(day.form for day in days)),
        form_high=max(MIN_FORM_SPAN, *(day.form for day in days)),
    )


def today_in(timezone: str) -> dt.date:
    return dt.datetime.now(ZoneInfo(timezone)).date()


def local_date(start_time: dt.datetime, timezone: str) -> dt.date:
    return start_time.astimezone(ZoneInfo(timezone)).date()


def load_view(
    rows: Iterable[ActivityRow], timezone: str, today: dt.date, days: int | None
) -> LoadView | None:
    dated = [(local_date(row.start_time, timezone), row.trimp) for row in rows]
    if not dated:
        return None
    daily: dict[dt.date, float] = {}
    for date, trimp in dated:
        daily[date] = daily.get(date, 0.0) + (trimp or 0.0)
    first = min(daily)
    last = max(today, max(daily))
    start = first if days is None else max(first, last - dt.timedelta(days=days - 1))
    frame = training_load(daily, start=first, end=last)
    window = [Day(**row) for row in frame.iter_rows(named=True) if row["date"] >= start]
    in_window = [trimp for date, trimp in dated if date >= start]
    return LoadView(
        days=window,
        activities=len(in_window),
        without_heart_rate=sum(trimp is None for trimp in in_window),
    )

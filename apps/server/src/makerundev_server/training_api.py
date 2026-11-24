import datetime as dt
from collections.abc import Sequence
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from makerundev_server import performance as current
from makerundev_server.api import Bounds, operation_id
from makerundev_server.performance import current_performance
from makerundev_server.store import Store
from makerundev_server.training import (
    DEFAULT_RANGE,
    RANGES,
    Day,
    LoadView,
    Range,
    load_ranges,
    load_view,
    today_in,
)

MAX_LOAD_DAYS = 1000


class LoadDay(BaseModel):
    date: dt.date
    trimp: float
    fitness: float
    fatigue: float
    form: float


class LoadWeek(BaseModel):
    week_ending: dt.date
    trimp: float
    fitness: float
    fatigue: float
    form: float


class LoadBounds(BaseModel):
    fitness_fatigue: Bounds
    form: Bounds


class Load(BaseModel):
    days: list[LoadDay]
    today: LoadDay
    weeks: list[LoadWeek]
    bounds: LoadBounds
    activities: int
    without_heart_rate: int


class PerformanceEffort(BaseModel):
    activity_id: int
    activity_name: str
    start_time: dt.datetime
    date: dt.date
    distance_m: float
    elapsed_s: float


class CriticalSpeedFit(BaseModel):
    speed_mps: float
    pace_s_per_km: float
    d_prime_m: float


class Performance(BaseModel):
    vdot: float | None
    vdot_effort: PerformanceEffort | None
    critical_speed: CriticalSpeedFit | None
    critical_speed_reason: Literal["too_few_efforts", "no_fit"] | None
    fitted: list[PerformanceEffort]
    excluded: int


class TrainingLoad(BaseModel):
    settings_set: bool
    load: Load | None
    performance: Performance | None


def router(store: Store) -> APIRouter:
    api = APIRouter(prefix="/api", generate_unique_id_function=operation_id)

    @api.get("/training-load", tags=["training-load"])
    def get_training_load(days: Range = DEFAULT_RANGE) -> TrainingLoad:
        settings = store.athlete_settings()
        timezone = settings.timezone if settings else "UTC"
        today = today_in(timezone)
        rows = store.list()
        view = load_view(rows, timezone, today, RANGES[days]) if settings else None
        found = current_performance(rows, timezone, today, store.performance.fill)
        return TrainingLoad(
            settings_set=settings is not None,
            load=_load(view) if view else None,
            performance=_performance(found) if found else None,
        )

    return api


def _day(day: Day) -> LoadDay:
    return LoadDay(
        date=day.date, trimp=day.load, fitness=day.fitness, fatigue=day.fatigue, form=day.form
    )


def _thinned(days: Sequence[Day]) -> list[Day]:
    if len(days) <= MAX_LOAD_DAYS:
        return list(days)
    last = len(days) - 1
    return [days[round(i * last / (MAX_LOAD_DAYS - 1))] for i in range(MAX_LOAD_DAYS)]


def _load(view: LoadView) -> Load:
    ranges = load_ranges(view.days)
    return Load(
        days=[_day(day) for day in _thinned(view.days)],
        today=_day(view.today),
        weeks=[
            LoadWeek(
                week_ending=day.date,
                trimp=trimp,
                fitness=day.fitness,
                fatigue=day.fatigue,
                form=day.form,
            )
            for day, trimp in view.weeks
        ],
        bounds=LoadBounds(
            fitness_fatigue=Bounds(low=0.0, high=ranges.load_top),
            form=Bounds(low=ranges.form_low, high=ranges.form_high),
        ),
        activities=view.activities,
        without_heart_rate=view.without_heart_rate,
    )


def _effort(effort: current.Effort) -> PerformanceEffort:
    return PerformanceEffort(
        activity_id=effort.activity_id,
        activity_name=effort.activity_name,
        start_time=effort.start_time,
        date=effort.date,
        distance_m=effort.distance_m,
        elapsed_s=effort.elapsed_s,
    )


def _performance(found: current.Performance) -> Performance:
    fit = found.critical_speed
    reason: Literal["too_few_efforts", "no_fit"] | None = None
    if fit is None:
        reason = "too_few_efforts" if found.too_few_efforts else "no_fit"
    return Performance(
        vdot=found.vdot,
        vdot_effort=_effort(found.vdot_source) if found.vdot_source else None,
        critical_speed=CriticalSpeedFit(
            speed_mps=fit.speed_mps, pace_s_per_km=1000 / fit.speed_mps, d_prime_m=fit.d_prime_m
        )
        if fit
        else None,
        critical_speed_reason=reason,
        fitted=[_effort(effort) for effort in found.fitted],
        excluded=found.excluded,
    )

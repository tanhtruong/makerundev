import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl

from makerundev.model import Activity

FloatArray = np.ndarray[Any, np.dtype[np.float64]]

MAX_GAP_S = 30.0
MOVING_SPEED_MPS = 0.5
ELEVATION_THRESHOLD_M = 3.0
GRADE_WINDOW_M = 60.0
MAX_RUNNING_GRADE = 0.45
MINETTI_COST = (155.4, -30.4, -43.3, 46.3, 19.5, 3.6)
FITNESS_DAYS = 42
FATIGUE_DAYS = 7
BANISTER_MALE = (0.64, 1.92)
BANISTER_FEMALE = (0.86, 1.67)
DEFAULT_ZONE_THRESHOLDS = (60.0, 70.0, 80.0, 90.0)
DEFAULT_EFFORT_DISTANCES_M = (400.0, 1000.0, 1609.344, 5000.0, 10000.0, 21097.5, 42195.0)
CRITICAL_SPEED_WINDOW_S = (120.0, 1200.0)


@dataclass(frozen=True, slots=True)
class Summary:
    distance_m: float
    elapsed_s: float
    moving_s: float
    pace_s_per_km: float | None
    grade_adjusted_pace_s_per_km: float | None
    avg_heart_rate: float | None
    max_heart_rate: float | None
    avg_cadence: float | None
    avg_power: float | None
    avg_ground_contact_time: float | None
    avg_vertical_oscillation: float | None
    avg_step_length: float | None
    elevation_gain_m: float
    elevation_loss_m: float


@dataclass(frozen=True, slots=True)
class Split:
    distance_m: float
    elapsed_s: float
    moving_s: float
    pace_s_per_km: float | None


@dataclass(frozen=True, slots=True)
class CriticalSpeed:
    speed_mps: float
    d_prime_m: float


@dataclass(frozen=True, slots=True)
class _Intervals:
    seconds: FloatArray
    meters: FloatArray
    recording: np.ndarray[Any, np.dtype[np.bool_]]
    moving: np.ndarray[Any, np.dtype[np.bool_]]


def _column(activity: Activity, name: str) -> FloatArray:
    if name not in activity.records.columns:
        return np.full(activity.records.height, np.nan)
    values: FloatArray = activity.records[name].cast(pl.Float64).fill_null(np.nan).to_numpy()
    return values


def _measured(activity: Activity, name: str) -> FloatArray:
    values = _column(activity, name)
    measured: FloatArray = np.where(values == 0, np.nan, values)
    return measured


def _elapsed(activity: Activity) -> FloatArray:
    micros: FloatArray = activity.records["timestamp"].dt.epoch("us").to_numpy().astype(np.float64)
    elapsed: FloatArray = (micros - micros[0]) / 1e6
    return elapsed


def _intervals(activity: Activity) -> _Intervals:
    seconds = np.diff(_elapsed(activity))
    meters = np.diff(_column(activity, "distance"))
    recording = seconds <= MAX_GAP_S
    with np.errstate(divide="ignore", invalid="ignore"):
        moving = recording & (meters / seconds >= MOVING_SPEED_MPS)
    return _Intervals(seconds, meters, recording, moving)


def _weighted_mean(values: FloatArray, weights: FloatArray) -> float | None:
    mask = ~np.isnan(values) & (weights > 0)
    if not mask.any():
        return None
    return float(np.average(values[mask], weights=weights[mask]))


def summarize(activity: Activity) -> Summary:
    steps = _intervals(activity)
    moving_weights = np.where(steps.moving, steps.seconds, 0.0)
    distance = float(np.nansum(steps.meters))
    moving_s = float(moving_weights.sum())
    heart_rate = _column(activity, "heart_rate")
    altitude = _column(activity, "altitude")
    gain, loss = elevation_change(altitude)
    return Summary(
        distance_m=distance,
        elapsed_s=float(_elapsed(activity)[-1]),
        moving_s=moving_s,
        pace_s_per_km=moving_s / (distance / 1000) if distance > 0 else None,
        grade_adjusted_pace_s_per_km=_grade_adjusted_pace(activity, steps, altitude),
        avg_heart_rate=_weighted_mean(heart_rate[:-1], moving_weights),
        max_heart_rate=float(np.nanmax(heart_rate)) if not np.isnan(heart_rate).all() else None,
        avg_cadence=_weighted_mean(_column(activity, "cadence")[:-1], moving_weights),
        avg_power=_weighted_mean(_column(activity, "power")[:-1], moving_weights),
        avg_ground_contact_time=_weighted_mean(
            _measured(activity, "ground_contact_time")[:-1], moving_weights
        ),
        avg_vertical_oscillation=_weighted_mean(
            _measured(activity, "vertical_oscillation")[:-1], moving_weights
        ),
        avg_step_length=_weighted_mean(_measured(activity, "step_length")[:-1], moving_weights),
        elevation_gain_m=gain,
        elevation_loss_m=loss,
    )


def grade_adjusted_pace(activity: Activity) -> float | None:
    return _grade_adjusted_pace(activity, _intervals(activity), _column(activity, "altitude"))


def _grade_adjusted_pace(
    activity: Activity, steps: _Intervals, altitude: FloatArray
) -> float | None:
    if not activity.sport.is_running:
        return None
    moving = np.flatnonzero(steps.moving)
    if moving.size == 0:
        return None
    if not (np.isfinite(altitude[moving]) & np.isfinite(altitude[moving + 1])).all():
        return None
    equivalent_m = 0.0
    for block in np.split(moving, np.flatnonzero(np.diff(moving) > 1) + 1):
        meters = steps.meters[block]
        distance = np.concatenate(([0.0], np.cumsum(meters)))
        heights = altitude[np.append(block, block[-1] + 1)]
        grade = np.clip(_window_grade(distance, heights), -MAX_RUNNING_GRADE, MAX_RUNNING_GRADE)
        cost = np.polyval(MINETTI_COST, grade)
        equivalent_m += float(np.sum(meters * cost)) / MINETTI_COST[-1]
    return float(steps.seconds[moving].sum()) * 1000 / equivalent_m


def _window_grade(distance: FloatArray, heights: FloatArray) -> FloatArray:
    total = distance[-1]
    centres = (distance[:-1] + distance[1:]) / 2
    left = np.clip(centres - GRADE_WINDOW_M / 2, 0.0, max(0.0, total - GRADE_WINDOW_M))
    right = np.minimum(left + GRADE_WINDOW_M, total)
    rise = np.interp(right, distance, heights) - np.interp(left, distance, heights)
    grade: FloatArray = rise / (right - left)
    return grade


def elevation_change(
    altitudes: Sequence[float] | FloatArray, threshold_m: float = ELEVATION_THRESHOLD_M
) -> tuple[float, float]:
    values = [float(a) for a in altitudes if not np.isnan(a)]
    if not values:
        return 0.0, 0.0
    gain = loss = 0.0
    pivot = candidate = values[0]
    trend = 0
    for altitude in values[1:]:
        if trend == 0:
            if abs(altitude - pivot) >= threshold_m:
                trend = 1 if altitude > pivot else -1
                candidate = altitude
        elif trend == 1:
            if altitude > candidate:
                candidate = altitude
            elif candidate - altitude >= threshold_m:
                gain += candidate - pivot
                pivot, candidate, trend = candidate, altitude, -1
        elif altitude < candidate:
            candidate = altitude
        elif altitude - candidate >= threshold_m:
            loss += pivot - candidate
            pivot, candidate, trend = candidate, altitude, 1
    if trend == 1:
        gain += candidate - pivot
    elif trend == -1:
        loss += pivot - candidate
    return gain, loss


def _at_distance(distance: FloatArray, values: FloatArray, targets: FloatArray) -> FloatArray:
    after = np.searchsorted(distance, targets, side="left")
    before = after - 1
    fraction = (targets - distance[before]) / (distance[after] - distance[before])
    interpolated: FloatArray = values[before] + fraction * (values[after] - values[before])
    return interpolated


def best_efforts(
    activity: Activity, distances_m: Sequence[float] = DEFAULT_EFFORT_DISTANCES_M
) -> dict[float, float]:
    elapsed = _elapsed(activity)
    distance = _column(activity, "distance")
    efforts: dict[float, float] = {}
    for target in distances_m:
        ends = distance + target
        starts = np.flatnonzero(ends <= distance[-1])
        if starts.size == 0:
            continue
        finish = _at_distance(distance, elapsed, ends[starts])
        efforts[target] = float(np.min(finish - elapsed[starts]))
    return efforts


def critical_speed(efforts: Mapping[float, float]) -> CriticalSpeed | None:
    shortest, longest = CRITICAL_SPEED_WINDOW_S
    kept = {d: t for d, t in efforts.items() if shortest <= t <= longest}
    times = np.array(list(kept.values()), dtype=np.float64)
    distances = np.array(list(kept.keys()), dtype=np.float64)
    if np.unique(times).size < 2:
        return None
    offsets = times - times.mean()
    speed = float(np.sum(offsets * (distances - distances.mean())) / np.sum(offsets * offsets))
    d_prime = float(distances.mean() - speed * times.mean())
    if speed <= 0 or d_prime <= 0:
        return None
    return CriticalSpeed(speed_mps=speed, d_prime_m=d_prime)


def splits(activity: Activity, every_m: float = 1000.0) -> list[Split]:
    distance = _column(activity, "distance")
    total = distance[-1] - distance[0]
    if total <= 0:
        return []
    elapsed = _elapsed(activity)
    steps = _intervals(activity)
    moving = np.concatenate(([0.0], np.cumsum(np.where(steps.moving, steps.seconds, 0.0))))
    marks = np.arange(1, int(total // every_m) + 1) * every_m
    marks = marks[marks < total]
    ends_m = np.append(marks, total)
    ends_elapsed = np.append(_at_distance(distance, elapsed, distance[0] + marks), elapsed[-1])
    ends_moving = np.append(_at_distance(distance, moving, distance[0] + marks), moving[-1])
    result = []
    for meters, elapsed_s, moving_s in zip(
        np.diff(ends_m, prepend=0.0),
        np.diff(ends_elapsed, prepend=0.0),
        np.diff(ends_moving, prepend=0.0),
        strict=True,
    ):
        result.append(
            Split(
                distance_m=float(meters),
                elapsed_s=float(elapsed_s),
                moving_s=float(moving_s),
                pace_s_per_km=float(moving_s / (meters / 1000)) if moving_s > 0 else None,
            )
        )
    return result


def time_in_zones(activity: Activity, boundaries_bpm: Sequence[float]) -> list[float]:
    steps = _intervals(activity)
    heart_rate = _column(activity, "heart_rate")[:-1]
    mask = steps.recording & ~np.isnan(heart_rate)
    zones = np.searchsorted(np.asarray(boundaries_bpm, dtype=np.float64), heart_rate[mask], "right")
    totals = np.bincount(zones, weights=steps.seconds[mask], minlength=len(boundaries_bpm) + 1)
    return [float(total) for total in totals]


def trimp(
    activity: Activity,
    resting_hr: float,
    max_hr: float,
    coefficients: tuple[float, float] = BANISTER_MALE,
) -> float:
    steps = _intervals(activity)
    heart_rate = _column(activity, "heart_rate")[:-1]
    mask = steps.recording & ~np.isnan(heart_rate)
    reserve = np.clip((heart_rate[mask] - resting_hr) / (max_hr - resting_hr), 0.0, 1.0)
    factor, exponent = coefficients
    minutes = steps.seconds[mask] / 60
    return float(np.sum(minutes * reserve * factor * np.exp(exponent * reserve)))


def aerobic_decoupling(activity: Activity) -> float | None:
    steps = _intervals(activity)
    heart_rate = _column(activity, "heart_rate")[:-1]
    mask = steps.moving & ~np.isnan(heart_rate)
    if not mask.any():
        return None
    seconds, meters, heart_rate = steps.seconds[mask], steps.meters[mask], heart_rate[mask]
    started = np.cumsum(seconds) - seconds
    first = started < seconds.sum() / 2
    halves = [first, ~first]
    if not all(half.any() for half in halves):
        return None
    efficiency = [
        (meters[half].sum() / seconds[half].sum())
        / np.average(heart_rate[half], weights=seconds[half])
        for half in halves
    ]
    return float((efficiency[0] - efficiency[1]) / efficiency[0] * 100)


def training_load(
    daily_loads: Mapping[dt.date, float],
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> pl.DataFrame:
    first = start or min(daily_loads)
    last = end or max(daily_loads)
    days = [first + dt.timedelta(days=offset) for offset in range((last - first).days + 1)]
    fitness = fatigue = 0.0
    rows = []
    for day in days:
        load = daily_loads.get(day, 0.0)
        form = fitness - fatigue
        fitness += (load - fitness) / FITNESS_DAYS
        fatigue += (load - fatigue) / FATIGUE_DAYS
        rows.append(
            {"date": day, "load": load, "fitness": fitness, "fatigue": fatigue, "form": form}
        )
    return pl.DataFrame(
        rows,
        schema={
            "date": pl.Date(),
            "load": pl.Float64(),
            "fitness": pl.Float64(),
            "fatigue": pl.Float64(),
            "form": pl.Float64(),
        },
    )

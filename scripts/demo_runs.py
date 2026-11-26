import datetime as dt
import math
import random
from dataclasses import dataclass, field
from typing import Literal

EARTH_RADIUS_M = 6_371_008.8
MOVING_CM_PER_S = 50
CLIMB_THRESHOLD_CM = 300
ALTITUDE_GRID_CM = 20
SPLIT_CM = 100_000
EFFORT_DISTANCES_M = (400.0, 1000.0, 1609.344, 3000.0, 5000.0, 10000.0, 21097.5, 42195.0)

DemoSport = Literal["running", "treadmill_running", "cycling"]
Format = Literal["fit", "gpx", "tcx"]


@dataclass(frozen=True, slots=True)
class Segment:
    seconds: int
    speed_cm_s: int = 0
    heart_rate: tuple[int, int] | None = None
    rise_cm: int = 0
    paused: bool = False
    lap: bool = False
    jump_cm: int = 0
    cadence: int | None = None
    power: int | None = None
    dynamics: tuple[int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class Route:
    latitude: float
    longitude: float
    legs: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class Run:
    slug: str
    name: str
    sport: DemoSport
    start: dt.datetime
    segments: tuple[Segment, ...]
    route: Route | None = None
    altitude_cm: int | None = None
    step_s: int = 1
    gps_noise_m: float = 0.0
    formats: tuple[Format, ...] = ("fit",)
    flaws: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class Sample:
    t: int
    distance_cm: int
    route_m: float
    altitude_cm: int | None
    heart_rate: int | None
    cadence: int | None
    power: int | None
    dynamics: tuple[int, int, int] | None
    speed_cm_s: int
    sideways_m: float


def samples(run: Run, rng: random.Random) -> list[Sample]:
    first = run.segments[0]
    altitude = run.altitude_cm
    out = [
        Sample(
            0,
            0,
            0.0,
            altitude,
            first.heart_rate[0] if first.heart_rate else None,
            first.cadence,
            first.power,
            first.dynamics,
            first.speed_cm_s,
            0.0,
        )
    ]
    t = distance = 0
    route_cm = 0
    peak = max((max(s.heart_rate) for s in run.segments if s.heart_rate), default=0)
    for segment in run.segments:
        if segment.seconds % run.step_s:
            raise ValueError(f"{run.slug}: segment length is not a multiple of the step")
        steps = 1 if segment.paused else segment.seconds // run.step_s
        step_s = segment.seconds // steps
        start_altitude = altitude
        waves = Wobble(
            rng.uniform(0.8, 2.0),
            rng.uniform(0, 2 * math.pi),
            rng.randint(3, 7),
            rng.uniform(0.3, 0.7),
            rng.uniform(0, 2 * math.pi),
        )
        for k in range(1, steps + 1):
            t += step_s
            moved = 0 if segment.paused else segment.speed_cm_s * step_s
            jump = segment.jump_cm * k // steps - segment.jump_cm * (k - 1) // steps
            distance += moved + jump
            route_cm += moved
            if start_altitude is not None:
                exact = start_altitude + segment.rise_cm * k / steps
                altitude = round(exact / ALTITUDE_GRID_CM) * ALTITUDE_GRID_CM
            out.append(
                Sample(
                    t,
                    distance,
                    route_cm / 100,
                    altitude,
                    _heart_rate(segment, k, steps, peak, waves),
                    _jitter(segment.cadence, 1, rng),
                    _jitter(segment.power, 6, rng),
                    segment.dynamics,
                    0 if segment.paused else (moved + jump) // step_s,
                    math.sin(math.pi * k / steps) * segment.jump_cm / 200,
                )
            )
    return out


@dataclass(frozen=True, slots=True)
class Wobble:
    slow: float
    slow_phase: float
    fast_periods: int
    fast: float
    fast_phase: float

    def at(self, fraction: float) -> float:
        turn = 2 * math.pi * fraction
        return self.slow * math.sin(turn + self.slow_phase) + self.fast * math.sin(
            self.fast_periods * turn + self.fast_phase
        )


def _heart_rate(segment: Segment, k: int, steps: int, peak: int, waves: Wobble) -> int | None:
    if segment.heart_rate is None:
        return None
    low, high = segment.heart_rate
    exact = low + (high - low) * k / steps
    if k == steps:
        return round(exact)
    bound = min(waves.slow + waves.fast, peak - exact)
    return round(exact + max(-bound, min(bound, waves.at(k / steps))))


def _jitter(value: int | None, spread: int, rng: random.Random) -> int | None:
    return None if value is None else value + rng.randint(-spread, spread)


def position(route: Route, metres: float, sideways_m: float) -> tuple[float, float]:
    latitude, longitude = route.latitude, route.longitude
    bearing = route.legs[-1][0]
    remaining = metres
    for leg_bearing, length in route.legs:
        bearing = leg_bearing
        step = min(remaining, length)
        latitude, longitude = _destination(latitude, longitude, bearing, step)
        remaining -= step
        if remaining <= 0:
            break
    if remaining > 0:
        latitude, longitude = _destination(latitude, longitude, bearing, remaining)
    if sideways_m:
        latitude, longitude = _destination(latitude, longitude, bearing + 90, sideways_m)
    return latitude, longitude


def offset(latitude: float, longitude: float, north_m: float, east_m: float) -> tuple[float, float]:
    latitude, longitude = _destination(latitude, longitude, 0.0, north_m)
    return _destination(latitude, longitude, 90.0, east_m)


def _destination(
    latitude: float, longitude: float, bearing: float, metres: float
) -> tuple[float, float]:
    lat, lon, theta = map(math.radians, (latitude, longitude, bearing))
    angle = metres / EARTH_RADIUS_M
    lat2 = math.asin(
        math.sin(lat) * math.cos(angle) + math.cos(lat) * math.sin(angle) * math.cos(theta)
    )
    lon2 = lon + math.atan2(
        math.sin(theta) * math.sin(angle) * math.cos(lat),
        math.cos(angle) - math.sin(lat) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)


def expected(run: Run) -> dict[str, object]:
    distance_cm = sum(_segment_cm(s) for s in run.segments)
    elapsed = sum(s.seconds for s in run.segments)
    moving = sum(s.seconds for s in run.segments if _moving(s))
    with_hr = [s for s in run.segments if _moving(s) and s.heart_rate]
    hr_seconds = sum(s.seconds for s in with_hr)
    avg_hr = (
        sum(s.seconds * (s.heart_rate[0] + s.heart_rate[1]) / 2 for s in with_hr if s.heart_rate)
        / hr_seconds
        if hr_seconds
        else None
    )
    peaks = [max(s.heart_rate) for s in run.segments if s.heart_rate]
    return {
        "distance_m": distance_cm / 100,
        "elapsed_s": float(elapsed),
        "moving_s": float(moving),
        "pace_s_per_km": moving / (distance_cm / 100_000) if distance_cm else None,
        "avg_heart_rate_bpm": avg_hr,
        "max_heart_rate_bpm": float(max(peaks)) if peaks else None,
        "elevation_gain_m": None if run.altitude_cm is None else _climb_cm(run) / 100,
        "splits": _splits(run),
        "laps": _laps(run),
        **_best_efforts(run, distance_cm / 100),
    }


def _best_efforts(run: Run, metres: float) -> dict[str, object]:
    speeds = {s.speed_cm_s for s in run.segments}
    if len(speeds) != 1 or any(s.paused or s.jump_cm for s in run.segments):
        return {}
    (speed,) = speeds
    return {
        "best_efforts": [
            {"distance_m": target, "elapsed_s": target / (speed / 100)}
            for target in EFFORT_DISTANCES_M
            if target <= metres
        ]
    }


def _segment_cm(segment: Segment) -> int:
    return 0 if segment.paused else segment.speed_cm_s * segment.seconds + segment.jump_cm


def _moving(segment: Segment) -> bool:
    return not segment.paused and segment.speed_cm_s >= MOVING_CM_PER_S


def _climb_cm(run: Run) -> int:
    runs: list[int] = []
    for segment in run.segments:
        if not segment.rise_cm:
            continue
        if runs and (runs[-1] > 0) == (segment.rise_cm > 0):
            runs[-1] += segment.rise_cm
        else:
            runs.append(segment.rise_cm)
    if any(abs(rise) <= CLIMB_THRESHOLD_CM for rise in runs):
        raise ValueError(f"{run.slug}: every rise and fall must be more than 3 m")
    if any(rise % ALTITUDE_GRID_CM for rise in runs):
        raise ValueError(f"{run.slug}: every rise and fall must sit on the 20 cm grid")
    return sum(rise for rise in runs if rise > 0)


def _splits(run: Run) -> list[dict[str, float | None]]:
    marks: list[tuple[float, float]] = []
    total_cm = elapsed = moving = 0.0
    next_mark = SPLIT_CM
    whole_cm = sum(_segment_cm(segment) for segment in run.segments)
    for segment in run.segments:
        length = _segment_cm(segment)
        while length and next_mark < whole_cm and total_cm + length >= next_mark:
            share = (next_mark - total_cm) / length
            marks.append(
                (
                    elapsed + share * segment.seconds,
                    moving + share * segment.seconds * _moving(segment),
                )
            )
            next_mark += SPLIT_CM
        total_cm += length
        elapsed += segment.seconds
        moving += segment.seconds * _moving(segment)
    marks.append((elapsed, moving))
    result: list[dict[str, float | None]] = []
    previous = (0.0, 0.0)
    for index, (at_elapsed, at_moving) in enumerate(marks):
        last = index == len(marks) - 1
        metres = (total_cm - index * SPLIT_CM) / 100 if last else SPLIT_CM / 100
        split_moving = at_moving - previous[1]
        result.append(
            {
                "distance_m": metres,
                "elapsed_s": at_elapsed - previous[0],
                "moving_s": split_moving,
                "pace_s_per_km": split_moving / (metres / 1000) if split_moving else None,
            }
        )
        previous = (at_elapsed, at_moving)
    return result


def laps(run: Run) -> list[tuple[int, int, int]]:
    if not any(segment.lap for segment in run.segments):
        return []
    result: list[tuple[int, int, int]] = []
    start = elapsed = distance = 0
    for index, segment in enumerate(run.segments):
        if segment.lap and index:
            result.append((start, elapsed, distance))
            start, elapsed, distance = start + elapsed, 0, 0
        elapsed += segment.seconds
        distance += _segment_cm(segment)
    result.append((start, elapsed, distance))
    return result


def _laps(run: Run) -> list[dict[str, float]]:
    return [
        {
            "distance_m": distance / 100,
            "elapsed_s": float(elapsed),
            "pace_s_per_km": elapsed / (distance / 100_000),
        }
        for _, elapsed, distance in laps(run)
        if distance
    ]

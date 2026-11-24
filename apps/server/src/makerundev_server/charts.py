import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl
from makerundev import format

from makerundev_server.training import Day, load_ranges

WIDTH = 720
HEIGHT = 160
INSET = 12
MAX_POINTS = 600


@dataclass(frozen=True, slots=True)
class Series:
    path: str
    low: float
    high: float


def series(records: pl.DataFrame, column: str, invert: bool = False) -> Series | None:
    if column == "pace":
        frame = records.filter(pl.col("speed") > 0.5).select(
            "distance", pace=1000 / pl.col("speed")
        )
    else:
        frame = records.select("distance", column).drop_nulls()
    if frame.height < 2:
        return None
    step = max(1, frame.height // MAX_POINTS)
    frame = frame.gather_every(step)
    x = frame["distance"].to_list()
    y = frame[column].to_list()
    x0, x1 = x[0], x[-1]
    low, high = min(y), max(y)
    span_x = (x1 - x0) or 1.0
    span_y = (high - low) or 1.0
    points = []
    for xi, yi in zip(x, y, strict=True):
        fraction = (yi - low) / span_y
        top = fraction if invert else 1 - fraction
        y_px = INSET + top * (HEIGHT - 2 * INSET)
        points.append(f"{(xi - x0) / span_x * WIDTH:.1f},{y_px:.1f}")
    return Series(path="M" + " L".join(points), low=low, high=high)


ROUTE_SIZE = 1000.0


@dataclass(frozen=True, slots=True)
class Route:
    points: str
    width: float
    height: float


def route_points(records: pl.DataFrame) -> list[tuple[float, float]] | None:
    positions = records.select("latitude", "longitude").drop_nulls()
    if positions.height < 2:
        return None
    step = max(1, math.ceil((positions.height - 1) / (MAX_POINTS - 1)))
    frame = positions.gather_every(step)
    if (positions.height - 1) % step:
        frame = pl.concat([frame, positions.tail(1)])
    return list(zip(frame["latitude"].to_list(), frame["longitude"].to_list(), strict=True))


def route(records: pl.DataFrame) -> Route | None:
    sampled = route_points(records)
    if sampled is None:
        return None
    lat = [point[0] for point in sampled]
    lon = [point[1] for point in sampled]
    squash = math.cos(math.radians(sum(lat) / len(lat)))
    x = [value * squash for value in lon]
    left, right = min(x), max(x)
    bottom, top = min(lat), max(lat)
    scale = ROUTE_SIZE / (max(right - left, top - bottom) or 1.0)
    points = " ".join(
        f"{INSET + (xi - left) * scale:.1f},{INSET + (top - yi) * scale:.1f}"
        for xi, yi in zip(x, lat, strict=True)
    )
    return Route(
        points=points,
        width=(right - left) * scale + 2 * INSET,
        height=(top - bottom) * scale + 2 * INSET,
    )


SERIES_BUCKETS = 500
SERIES_VALUES = ("pace_s_per_km", "heart_rate_bpm", "altitude_m")


@dataclass(frozen=True, slots=True)
class SeriesRow:
    distance_m: float
    elapsed_s: float
    pace_s_per_km: float | None
    heart_rate_bpm: float | None
    altitude_m: float | None


@dataclass(frozen=True, slots=True)
class Bounds:
    low: float
    high: float


@dataclass(frozen=True, slots=True)
class SeriesBounds:
    pace_s_per_km: Bounds | None
    heart_rate_bpm: Bounds | None
    altitude_m: Bounds | None


def _chart_frame(records: pl.DataFrame) -> pl.DataFrame:
    return (
        records.with_columns(
            elapsed_s=(pl.col("timestamp") - pl.col("timestamp").first()).dt.total_microseconds()
            / 1e6
        )
        .filter(pl.col("distance").is_not_null())
        .select(
            distance_m=pl.col("distance"),
            elapsed_s=pl.col("elapsed_s"),
            pace_s_per_km=pl.when(pl.col("speed") > 0.5).then(1000 / pl.col("speed")),
            heart_rate_bpm=pl.col("heart_rate"),
            altitude_m=pl.col("altitude"),
        )
    )


def chart_series(records: pl.DataFrame) -> list[SeriesRow]:
    frame = _chart_frame(records)
    if frame.height < 2:
        return []
    if frame.height <= 2 * SERIES_BUCKETS:
        return [SeriesRow(**row) for row in frame.iter_rows(named=True)]
    low, high = frame.select(low=pl.col("distance_m").min(), high=pl.col("distance_m").max()).row(0)
    span = (high - low) or 1.0
    bucket = ((pl.col("distance_m") - low) / span * SERIES_BUCKETS).floor()
    buckets = (
        frame.with_columns(bucket=bucket.clip(upper_bound=SERIES_BUCKETS - 1))
        .group_by("bucket", maintain_order=True)
        .agg(
            pl.len().alias("samples"),
            pl.col("distance_m", "elapsed_s").first().name.suffix("_first"),
            pl.col("distance_m", "elapsed_s").last().name.suffix("_last"),
            pl.col(SERIES_VALUES).min().name.suffix("_min"),
            pl.col(SERIES_VALUES).max().name.suffix("_max"),
            pl.col(SERIES_VALUES).arg_min().name.suffix("_at_min"),
            pl.col(SERIES_VALUES).arg_max().name.suffix("_at_max"),
        )
    )
    rows = []
    for group in buckets.iter_rows(named=True):
        first: dict[str, float | None] = {}
        last: dict[str, float | None] = {}
        for name in SERIES_VALUES:
            lowest, highest = group[f"{name}_min"], group[f"{name}_max"]
            rising = lowest is None or group[f"{name}_at_min"] <= group[f"{name}_at_max"]
            first[name], last[name] = (lowest, highest) if rising else (highest, lowest)
        rows.append(SeriesRow(group["distance_m_first"], group["elapsed_s_first"], **first))
        if group["samples"] > 1:
            rows.append(SeriesRow(group["distance_m_last"], group["elapsed_s_last"], **last))
    return rows


def series_bounds(records: pl.DataFrame) -> SeriesBounds:
    frame = _chart_frame(records)

    def bounds(name: str, low: float, high: float) -> Bounds | None:
        values = pl.col(name).drop_nulls()
        lowest, highest = frame.select(
            values.quantile(low, "linear"), values.quantile(high, "linear").alias("high")
        ).row(0)
        return None if lowest is None else Bounds(low=lowest, high=highest)

    return SeriesBounds(
        pace_s_per_km=bounds("pace_s_per_km", 0.02, 0.98),
        heart_rate_bpm=bounds("heart_rate_bpm", 0.0, 1.0),
        altitude_m=bounds("altitude_m", 0.0, 1.0),
    )


@dataclass(frozen=True, slots=True)
class ZoneBar:
    name: str
    bpm: str
    seconds: float
    share: float


def zone_bars(seconds: Sequence[float], boundaries_bpm: Sequence[float]) -> list[ZoneBar]:
    total = sum(seconds)
    if not total:
        return []
    return [
        ZoneBar(
            f"Zone {zone + 1}",
            format.zone_range(zone, boundaries_bpm),
            zone_seconds,
            zone_seconds / total,
        )
        for zone, zone_seconds in enumerate(seconds)
    ]


@dataclass(frozen=True, slots=True)
class Hit:
    x: float
    width: float
    title: str


@dataclass(frozen=True, slots=True)
class Line:
    path: str
    end: float


LABEL_GAP = 12.0


def spread_labels(ends: dict[str, float]) -> list[tuple[str, float]]:
    placed: list[tuple[str, float]] = []
    for name, top in sorted(ends.items(), key=lambda item: item[1]):
        top = max(top, placed[-1][1] + LABEL_GAP if placed else LABEL_GAP)
        placed.append((name, top))
    overflow = placed[-1][1] - 100.0 if placed else 0.0
    if overflow > 0:
        placed = [(name, top - overflow) for name, top in placed]
    return placed


@dataclass(frozen=True, slots=True)
class LoadChart:
    fitness: Line
    fatigue: Line
    form: Line
    load_top: float
    form_low: float
    form_high: float
    zero: float
    hits: list[Hit]

    @property
    def end_labels(self) -> list[tuple[str, float]]:
        return spread_labels({"Fitness": self.fitness.end, "Fatigue": self.fatigue.end})


def load_chart(days: Sequence[Day]) -> LoadChart:
    last = len(days) - 1
    indices = list(range(0, len(days), max(1, len(days) // MAX_POINTS)))
    if indices[-1] != last:
        indices.append(last)
    sampled = [days[index] for index in indices]
    xs = [index / last * WIDTH for index in indices] if last else [WIDTH / 2]
    ranges = load_ranges(days)
    load_top, form_low, form_high = ranges.load_top, ranges.form_low, ranges.form_high

    def y(value: float, low: float, high: float) -> float:
        fraction = (value - low) / ((high - low) or 1.0)
        return INSET + (1 - fraction) * (HEIGHT - 2 * INSET)

    def line(key: str, low: float, high: float) -> Line:
        values = [getattr(day, key) for day in sampled]
        points = [f"{x:.1f},{y(v, low, high):.1f}" for x, v in zip(xs, values, strict=True)]
        if len(points) == 1:
            points = [f"0,{y(values[0], low, high):.1f}", f"{WIDTH},{y(values[0], low, high):.1f}"]
        return Line(path="M" + " L".join(points), end=y(values[-1], low, high) / HEIGHT * 100)

    edges = [0.0, *((a + b) / 2 for a, b in itertools.pairwise(xs)), float(WIDTH)]
    hits = [
        Hit(
            x=edges[position],
            width=edges[position + 1] - edges[position],
            title=(
                f"{day.date:%Y-%m-%d}: fitness {day.fitness:.0f}, fatigue {day.fatigue:.0f}, "
                f"form {round(day.form):+d}, TRIMP {day.load:.0f}"
            ),
        )
        for position, day in enumerate(sampled)
    ]
    return LoadChart(
        fitness=line("fitness", 0.0, load_top),
        fatigue=line("fatigue", 0.0, load_top),
        form=line("form", form_low, form_high),
        load_top=load_top,
        form_low=form_low,
        form_high=form_high,
        zero=y(0.0, form_low, form_high),
        hits=hits,
    )

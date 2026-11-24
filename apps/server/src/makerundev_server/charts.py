import math
from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl

MAX_POINTS = 600


def route_points(records: pl.DataFrame) -> list[tuple[float, float]] | None:
    positions = records.select("latitude", "longitude").drop_nulls()
    if positions.height < 2:
        return None
    step = max(1, math.ceil((positions.height - 1) / (MAX_POINTS - 1)))
    frame = positions.gather_every(step)
    if (positions.height - 1) % step:
        frame = pl.concat([frame, positions.tail(1)])
    return list(zip(frame["latitude"].to_list(), frame["longitude"].to_list(), strict=True))


ROUTE_SIZE = 1000.0


@dataclass(frozen=True, slots=True)
class RouteShape:
    points: list[tuple[float, float]]
    width: float
    height: float


def route_shape(positions: Sequence[tuple[float, float]]) -> RouteShape:
    lat = [point[0] for point in positions]
    squash = math.cos(math.radians(sum(lat) / len(lat)))
    x = [point[1] * squash for point in positions]
    left, top = min(x), max(lat)
    width, height = max(x) - left, top - min(lat)
    scale = ROUTE_SIZE / (max(width, height) or 1.0)
    return RouteShape(
        points=[((xi - left) * scale, (top - yi) * scale) for xi, yi in zip(x, lat, strict=True)],
        width=width * scale,
        height=height * scale,
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

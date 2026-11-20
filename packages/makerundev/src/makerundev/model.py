import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

import numpy as np
import polars as pl

from makerundev.errors import ActivityFileError

SourceFormat = Literal["fit", "gpx", "tcx", "strava", "rows"]

EARTH_RADIUS_M = 6_371_008.8

STREAM_SCHEMA: dict[str, pl.DataType] = {
    "timestamp": pl.Datetime("us", "UTC"),
    "latitude": pl.Float64(),
    "longitude": pl.Float64(),
    "distance": pl.Float64(),
    "speed": pl.Float64(),
    "altitude": pl.Float64(),
    "heart_rate": pl.Float64(),
    "cadence": pl.Float64(),
    "power": pl.Float64(),
    "temperature": pl.Float64(),
}


class Sport(StrEnum):
    RUNNING = "running"
    TRAIL_RUNNING = "trail_running"
    TREADMILL_RUNNING = "treadmill_running"
    WALKING = "walking"
    HIKING = "hiking"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    OTHER = "other"

    @property
    def is_running(self) -> bool:
        return self in {Sport.RUNNING, Sport.TRAIL_RUNNING, Sport.TREADMILL_RUNNING}


@dataclass(frozen=True, slots=True)
class Lap:
    start_time: dt.datetime
    elapsed_s: float | None = None
    distance_m: float | None = None


@dataclass(frozen=True, slots=True)
class Activity:
    sport: Sport
    start_time: dt.datetime
    records: pl.DataFrame
    source_format: SourceFormat = "rows"
    device: str | None = None
    laps: tuple[Lap, ...] = ()

    @classmethod
    def from_rows(
        cls,
        rows: Iterable[Mapping[str, Any]],
        sport: Sport,
        source_format: SourceFormat = "rows",
        device: str | None = None,
        start_time: dt.datetime | None = None,
        laps: Iterable[Lap] = (),
    ) -> "Activity":
        records = normalize_records(rows)
        first: dt.datetime = records["timestamp"][0]
        return cls(
            sport=sport,
            start_time=start_time or first,
            records=records,
            source_format=source_format,
            device=device,
            laps=tuple(sorted(laps, key=lambda lap: lap.start_time)),
        )


def normalize_records(rows: Iterable[Mapping[str, Any]]) -> pl.DataFrame:
    frame = pl.from_dicts(list(rows), schema=STREAM_SCHEMA, strict=False)
    frame = (
        frame.filter(pl.col("timestamp").is_not_null())
        .sort("timestamp")
        .unique("timestamp", keep="first", maintain_order=True)
    )
    if frame.is_empty():
        raise ActivityFileError("the file contains no timestamped records")
    if frame["distance"].null_count() == frame.height:
        frame = frame.with_columns(distance=pl.Series(_distance_from_positions(frame)))
    frame = frame.with_columns(pl.col("distance").forward_fill().fill_null(0.0).cum_max())
    if frame["speed"].null_count() == frame.height:
        seconds = pl.col("timestamp").diff().dt.total_microseconds() / 1e6
        frame = frame.with_columns(speed=pl.col("distance").diff() / seconds)
    return frame


def _distance_from_positions(frame: pl.DataFrame) -> np.ndarray[Any, np.dtype[np.float64]]:
    lat = np.radians(frame["latitude"].to_numpy().astype(np.float64))
    lon = np.radians(frame["longitude"].to_numpy().astype(np.float64))
    lat, lon = _forward_fill(lat), _forward_fill(lon)
    dlat = np.diff(lat)
    dlon = np.diff(lon)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(dlon / 2) ** 2
    steps = 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))
    return np.concatenate([[0.0], np.cumsum(np.nan_to_num(steps))])


def _forward_fill(
    values: np.ndarray[Any, np.dtype[np.float64]],
) -> np.ndarray[Any, np.dtype[np.float64]]:
    valid = ~np.isnan(values)
    index = np.where(valid, np.arange(values.size), 0)
    np.maximum.accumulate(index, out=index)
    return values[index]

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from makerundev import Sport
from sqlalchemy import ColumnElement, UnaryExpression, func, or_

from makerundev_server.db import ActivityRow

ActivitySort = Literal[
    "start_time",
    "-start_time",
    "distance_m",
    "-distance_m",
    "moving_s",
    "-moving_s",
    "pace_s_per_km",
    "-pace_s_per_km",
    "avg_heart_rate_bpm",
    "-avg_heart_rate_bpm",
    "elevation_gain_m",
    "-elevation_gain_m",
    "trimp",
    "-trimp",
]
SORT_COLUMNS = {
    "start_time": ActivityRow.start_time,
    "distance_m": ActivityRow.distance_m,
    "moving_s": ActivityRow.moving_s,
    "pace_s_per_km": ActivityRow.pace_s_per_km,
    "avg_heart_rate_bpm": ActivityRow.avg_heart_rate,
    "elevation_gain_m": ActivityRow.elevation_gain_m,
    "trimp": ActivityRow.trimp,
}


@dataclass(frozen=True, slots=True)
class ActivityFilter:
    text: str = ""
    sports: Sequence[Sport] = ()
    min_distance_m: float | None = None
    max_distance_m: float | None = None
    starts_from: dt.datetime | None = None
    starts_before: dt.datetime | None = None


def conditions(wanted: ActivityFilter) -> list[ColumnElement[bool]]:
    found: list[ColumnElement[bool]] = []
    if wanted.text:
        literal = wanted.text.casefold()
        for special in ("\\", "%", "_"):
            literal = literal.replace(special, f"\\{special}")
        pattern = f"%{literal}%"
        found.append(
            or_(
                func.casefold(ActivityRow.name).like(pattern, escape="\\"),
                func.casefold(ActivityRow.filename).like(pattern, escape="\\"),
            )
        )
    if wanted.sports:
        found.append(ActivityRow.sport.in_([sport.value for sport in wanted.sports]))
    if wanted.min_distance_m is not None:
        found.append(ActivityRow.distance_m >= wanted.min_distance_m)
    if wanted.max_distance_m is not None:
        found.append(ActivityRow.distance_m <= wanted.max_distance_m)
    if wanted.starts_from is not None:
        found.append(ActivityRow.start_time >= wanted.starts_from)
    if wanted.starts_before is not None:
        found.append(ActivityRow.start_time < wanted.starts_before)
    return found


def ordering(sort: ActivitySort) -> tuple[UnaryExpression[Any], ...]:
    descending = sort.startswith("-")
    column = SORT_COLUMNS[sort.removeprefix("-")]
    if descending:
        return column.desc().nulls_last(), ActivityRow.id.desc()
    return column.asc().nulls_last(), ActivityRow.id.asc()

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from makerundev_server.db import ActivityRow

MATCH_SECONDS = 60.0
MATCH_DISTANCE_M = 200.0
MATCH_DISTANCE_SHARE = 0.05


def same_activity(
    start: dt.datetime, distance_m: float, other_start: dt.datetime, other_distance_m: float
) -> bool:
    if abs((start - other_start).total_seconds()) > MATCH_SECONDS:
        return False
    allowed = max(MATCH_DISTANCE_M, MATCH_DISTANCE_SHARE * max(distance_m, other_distance_m))
    return abs(distance_m - other_distance_m) <= allowed


def nearby(session: Session, start: dt.datetime) -> list[ActivityRow]:
    window = dt.timedelta(seconds=MATCH_SECONDS)
    return list(
        session.scalars(
            select(ActivityRow)
            .where(ActivityRow.start_time.between(start - window, start + window))
            .order_by(ActivityRow.id)
        )
    )


def strava_id_in(filename: str) -> str | None:
    stem = filename.split(".", 1)[0]
    return stem if stem.isdigit() else None

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from makerundev_server.db import STRAVA, ActivityRow

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


def file_match(
    session: Session, strava_id: str, start: dt.datetime, distance_m: float
) -> ActivityRow | None:
    files = (ActivityRow.sha256.is_not(None), ActivityRow.external_id.is_(None))
    named = session.scalars(
        select(ActivityRow).where(*files, ActivityRow.filename.like(f"{strava_id}.%"))
    ).first()
    if named is not None:
        return named
    for row in nearby(session, start):
        if (
            row.sha256 is not None
            and row.external_id is None
            and same_activity(start, distance_m, row.start_time, row.distance_m)
        ):
            return row
    return None


def synced_match(
    session: Session, filename: str, start: dt.datetime, distance_m: float
) -> ActivityRow | None:
    synced = (ActivityRow.sha256.is_(None), ActivityRow.external_source == STRAVA)
    strava_id = strava_id_in(filename)
    if strava_id is not None:
        named = session.scalars(
            select(ActivityRow).where(*synced, ActivityRow.external_id == strava_id)
        ).first()
        if named is not None:
            return named
    for row in nearby(session, start):
        if (
            row.sha256 is None
            and row.external_source == STRAVA
            and same_activity(start, distance_m, row.start_time, row.distance_m)
        ):
            return row
    return None

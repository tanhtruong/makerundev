import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.routing import APIRoute
from makerundev import Sport
from makerundev.model import SourceFormat
from pydantic import BaseModel

from makerundev_server.db import ActivityRow
from makerundev_server.lookups import activity_or_404
from makerundev_server.store import Store

DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200


def operation_id(route: APIRoute) -> str:
    first, *rest = route.name.split("_")
    return first + "".join(word.capitalize() for word in rest)


class Problem(BaseModel):
    detail: str


class ActivitySummary(BaseModel):
    id: int
    name: str | None
    filename: str
    sport: Sport
    device: str | None
    source_format: SourceFormat
    start_time: dt.datetime
    distance_m: float
    elapsed_s: float
    moving_s: float
    pace_s_per_km: float | None
    avg_heart_rate_bpm: float | None
    max_heart_rate_bpm: float | None
    elevation_gain_m: float
    trimp: float | None
    external_source: str | None
    external_id: str | None


class ActivityPage(BaseModel):
    items: list[ActivitySummary]
    total: int


def router(store: Store) -> APIRouter:
    api = APIRouter(prefix="/api", generate_unique_id_function=operation_id)
    not_found: dict[int | str, dict[str, Any]] = {
        404: {"model": Problem, "description": "No activity has this id"}
    }

    @api.get("/activities", tags=["activities"])
    def list_activities(
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> ActivityPage:
        rows, total = store.page(limit, offset)
        return ActivityPage(items=[_summary(row) for row in rows], total=total)

    @api.get("/activities/{activity_id}/records", tags=["activities"], responses=not_found)
    def list_activity_records(activity_id: int) -> list[dict[str, Any]]:
        return store.records(activity_or_404(store, activity_id)).to_dicts()

    return api


def _summary(row: ActivityRow) -> ActivitySummary:
    return ActivitySummary(
        id=row.id,
        name=row.name,
        filename=row.filename,
        sport=Sport(row.sport),
        device=row.device,
        source_format=row.source_format,
        start_time=row.start_time,
        distance_m=row.distance_m,
        elapsed_s=row.elapsed_s,
        moving_s=row.moving_s,
        pace_s_per_km=row.pace_s_per_km,
        avg_heart_rate_bpm=row.avg_heart_rate,
        max_heart_rate_bpm=row.max_heart_rate,
        elevation_gain_m=row.elevation_gain_m,
        trimp=row.trimp,
        external_source=row.external_source,
        external_id=row.external_id,
    )

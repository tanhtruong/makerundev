import datetime as dt
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.routing import APIRoute
from makerundev import Sport, format
from makerundev.metrics import (
    aerobic_decoupling,
    best_efforts,
    estimated_power,
    splits,
    summarize,
    time_in_zones,
)
from makerundev.model import Activity, SourceFormat
from makerundev.model import Lap as RecordedLap
from pydantic import BaseModel

from makerundev_server import charts
from makerundev_server.db import ActivityRow
from makerundev_server.lookups import activity_or_404
from makerundev_server.performance import COUNTED_SPORTS
from makerundev_server.settings import AthleteSettings
from makerundev_server.store import Store
from makerundev_server.strava import ACTIVITY_URL

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


class RunningDynamics(BaseModel):
    ground_contact_time_ms: float | None
    vertical_oscillation_mm: float | None
    step_length_m: float | None


class Split(BaseModel):
    distance_m: float
    elapsed_s: float
    moving_s: float
    pace_s_per_km: float | None


class Lap(BaseModel):
    number: int
    distance_m: float | None
    elapsed_s: float | None
    pace_s_per_km: float | None


class BestEffort(BaseModel):
    distance_m: float
    elapsed_s: float


class Zone(BaseModel):
    name: str
    low_bpm: int | None
    high_bpm: int | None
    elapsed_s: float
    share: float


class SeriesRow(BaseModel):
    distance_m: float
    elapsed_s: float
    pace_s_per_km: float | None
    heart_rate_bpm: float | None
    altitude_m: float | None


class Bounds(BaseModel):
    low: float
    high: float


class SeriesBounds(BaseModel):
    pace_s_per_km: Bounds | None
    heart_rate_bpm: Bounds | None
    altitude_m: Bounds | None


class RoutePoint(BaseModel):
    latitude_deg: float
    longitude_deg: float


class ActivityDetail(ActivitySummary):
    strava_url: str | None
    is_running: bool
    settings_set: bool
    body_mass_kg: float | None
    counts_for_performance: bool
    excluded_from_performance: bool
    grade_adjusted_pace_s_per_km: float | None
    aerobic_decoupling_percent: float | None
    avg_power_w: float | None
    avg_power_w_per_kg: float | None
    estimated_power_w: float | None
    estimated_power_w_per_kg: float | None
    running_dynamics: RunningDynamics
    splits: list[Split]
    laps: list[Lap]
    best_efforts: list[BestEffort]
    zones: list[Zone]
    series: list[SeriesRow]
    series_bounds: SeriesBounds
    route: list[RoutePoint] | None


class Exclusion(BaseModel):
    excluded: bool


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

    @api.get("/activities/{activity_id}", tags=["activities"], responses=not_found)
    def get_activity(activity_id: int) -> ActivityDetail:
        row = activity_or_404(store, activity_id)
        return _detail(row, store.activity(row), store.laps(row), store.athlete_settings())

    @api.put(
        "/activities/{activity_id}/exclusion",
        tags=["activities"],
        responses={
            **not_found,
            409: {"model": Problem, "description": "The sport does not count towards performance"},
        },
    )
    def set_activity_exclusion(activity_id: int, exclusion: Exclusion) -> Exclusion:
        row = activity_or_404(store, activity_id)
        if row.sport not in COUNTED_SPORTS:
            raise HTTPException(
                status_code=409, detail="activity does not count towards performance"
            )
        store.performance.exclude(activity_id, exclusion.excluded)
        return exclusion

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


def unless_single[T](rows: Sequence[T]) -> list[T]:
    return list(rows) if len(rows) >= 2 else []


def _per_kg(watts: float | None, body_mass_kg: float | None) -> float | None:
    return watts / body_mass_kg if watts is not None and body_mass_kg is not None else None


def _zones(activity: Activity, settings: AthleteSettings | None) -> list[Zone]:
    if settings is None:
        return []
    boundaries = settings.zone_boundaries_bpm()
    seconds = time_in_zones(activity, boundaries)
    total = sum(seconds)
    if not total:
        return []
    starts = format.zone_starts(boundaries)
    return [
        Zone(
            name=f"Zone {zone + 1}",
            low_bpm=starts[zone - 1] if zone else None,
            high_bpm=starts[zone] - 1 if zone < len(starts) else None,
            elapsed_s=zone_seconds,
            share=zone_seconds / total,
        )
        for zone, zone_seconds in enumerate(seconds)
    ]


def _detail(
    row: ActivityRow,
    activity: Activity,
    laps: Sequence[RecordedLap],
    settings: AthleteSettings | None,
) -> ActivityDetail:
    summary = summarize(activity)
    body_mass_kg = settings.body_mass_kg if settings else None
    estimated = estimated_power(activity, body_mass_kg) if body_mass_kg is not None else None
    records = activity.records
    route = charts.route_points(records)
    bounds = charts.series_bounds(records)
    return ActivityDetail(
        **_summary(row).model_dump(),
        strava_url=ACTIVITY_URL.format(row.external_id)
        if row.external_source == "strava"
        else None,
        is_running=activity.sport.is_running,
        settings_set=settings is not None,
        body_mass_kg=body_mass_kg,
        counts_for_performance=row.sport in COUNTED_SPORTS,
        excluded_from_performance=row.excluded_from_performance,
        grade_adjusted_pace_s_per_km=summary.grade_adjusted_pace_s_per_km,
        aerobic_decoupling_percent=aerobic_decoupling(activity),
        avg_power_w=summary.avg_power,
        avg_power_w_per_kg=_per_kg(summary.avg_power, body_mass_kg),
        estimated_power_w=estimated,
        estimated_power_w_per_kg=_per_kg(estimated, body_mass_kg),
        running_dynamics=RunningDynamics(
            ground_contact_time_ms=summary.avg_ground_contact_time,
            vertical_oscillation_mm=summary.avg_vertical_oscillation,
            step_length_m=summary.avg_step_length,
        ),
        splits=[
            Split.model_validate(split, from_attributes=True)
            for split in unless_single(splits(activity))
        ],
        laps=[
            Lap(
                number=number,
                distance_m=lap.distance_m,
                elapsed_s=lap.elapsed_s,
                pace_s_per_km=lap.pace_s_per_km,
            )
            for number, lap in enumerate(unless_single(laps), start=1)
        ],
        best_efforts=[
            BestEffort(distance_m=distance, elapsed_s=seconds)
            for distance, seconds in best_efforts(activity).items()
        ],
        zones=_zones(activity, settings),
        series=[
            SeriesRow.model_validate(point, from_attributes=True)
            for point in charts.chart_series(records)
        ],
        series_bounds=SeriesBounds.model_validate(bounds, from_attributes=True),
        route=[RoutePoint(latitude_deg=lat, longitude_deg=lon) for lat, lon in route]
        if route is not None
        else None,
    )

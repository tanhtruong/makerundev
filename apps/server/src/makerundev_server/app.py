import datetime as dt
import secrets
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx2
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from makerundev import Lap, format
from makerundev.metrics import (
    aerobic_decoupling,
    best_efforts,
    estimated_power,
    splits,
    summarize,
    time_in_zones,
)

from makerundev_server import (
    api,
    charts,
    config,
    garmin,
    garmin_api,
    settings_api,
    strava_api,
    training_api,
    web,
)
from makerundev_server.cross_site import CrossSiteGuard
from makerundev_server.db import connect
from makerundev_server.lookups import activity_or_404
from makerundev_server.performance import COUNTED_SPORTS
from makerundev_server.store import Store
from makerundev_server.strava import ACTIVITY_URL, SCOPE, StravaClient, StravaError

HERE = Path(__file__).parent


def create_app(
    data_dir: Path | None = None,
    strava_transport: httpx2.BaseTransport | None = None,
    garmin_transport: httpx2.BaseTransport | None = None,
    garmin_pause: float = garmin.PAUSE_S,
    web_dir: Path | None = None,
) -> FastAPI:
    root = data_dir or config.data_dir()
    root.mkdir(parents=True, exist_ok=True)
    store = Store(root, connect(root))
    store.reset_syncs()
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.filters.update(
        km=format.distance,
        duration=format.duration,
        pace=format.pace,
        decoupling=format.decoupling,
        power=format.power,
        distance_name=format.distance_name,
        local=_local,
    )
    templates.env.globals.update(
        format_pace=format.pace,
        format_bpm=lambda value: f"{value:.0f} bpm",
        format_metres=lambda value: f"{value:.0f} m",
    )

    app = FastAPI(title="makerundev", version="pre-1.0")
    pages = APIRouter(include_in_schema=False)
    app.add_middleware(CrossSiteGuard)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    @pages.get("/activities/{activity_id}", response_class=HTMLResponse)
    def detail(request: Request, activity_id: int) -> HTMLResponse:
        row = activity_or_404(store, activity_id)
        activity = store.activity(row)
        records = activity.records
        summary = summarize(activity)
        settings = store.athlete_settings()
        body_mass_kg = settings.body_mass_kg if settings else None
        zones = []
        if settings is not None:
            boundaries = settings.zone_boundaries_bpm()
            zones = charts.zone_bars(time_in_zones(activity, boundaries), boundaries)
        return templates.TemplateResponse(
            request,
            "activity.html",
            {
                "activity": row,
                "strava_url": ACTIVITY_URL.format(row.external_id)
                if row.external_source == "strava"
                else None,
                "is_running": activity.sport.is_running,
                "counts_for_performance": row.sport in COUNTED_SPORTS,
                "grade_adjusted_pace": summary.grade_adjusted_pace_s_per_km,
                "decoupling": aerobic_decoupling(activity),
                "avg_power": summary.avg_power,
                "body_mass_kg": body_mass_kg,
                "estimated_power": estimated_power(activity, body_mass_kg)
                if body_mass_kg is not None
                else None,
                "efforts": best_efforts(activity),
                "splits": api.unless_single(splits(activity)),
                "laps": _lap_rows(store.laps(row)),
                "ground_contact_time": summary.avg_ground_contact_time,
                "vertical_oscillation": summary.avg_vertical_oscillation,
                "step_length": summary.avg_step_length,
                "settings_set": settings is not None,
                "zones": zones,
                "timezone": settings.timezone if settings else "UTC",
                "route": charts.route(records),
                "pace": charts.series(records, "pace", invert=True),
                "heart_rate": charts.series(records, "heart_rate"),
                "elevation": charts.series(records, "altitude"),
                "chart": {"width": charts.WIDTH, "height": charts.HEIGHT},
            },
        )

    @pages.post("/activities/{activity_id}/exclusion", response_model=None)
    async def exclusion(request: Request, activity_id: int) -> Response:
        excluded = (await request.form()).get("excluded") == "true"
        if not await run_in_threadpool(store.performance.exclude, activity_id, excluded):
            raise HTTPException(status_code=404, detail="activity not found")
        return RedirectResponse(f"/activities/{activity_id}", status_code=303)

    def strava_client() -> StravaClient | None:
        return strava_api.strava_client(strava_transport)

    def to_strava(notice: str = "") -> RedirectResponse:
        return RedirectResponse(f"/strava?notice={notice}" if notice else "/strava", 303)

    @pages.post("/strava/connect", response_model=None)
    def strava_connect(request: Request) -> Response:
        client = strava_client()
        if client is None:
            return to_strava()
        state = secrets.token_urlsafe(32)
        store.begin_strava_oauth(state)
        redirect_uri = str(request.url_for("strava_callback"))
        return RedirectResponse(client.authorize_url(redirect_uri, state), status_code=303)

    @pages.get("/strava/callback", name="strava_callback", response_model=None)
    def strava_callback(
        code: str = "", state: str = "", scope: str = "", error: str = ""
    ) -> Response:
        client = strava_client()
        connection = store.strava_connection()
        expected = connection.oauth_state if connection else None
        if client is None or not expected or not secrets.compare_digest(expected, state):
            return to_strava("state")
        if error or not code:
            return to_strava("denied")
        if SCOPE not in scope.replace(" ", ",").split(","):
            return to_strava("scope")
        try:
            tokens = client.exchange(code)
        except (StravaError, httpx2.HTTPError, KeyError):
            return to_strava("failed")
        store.save_strava_tokens(tokens)
        return to_strava("connected")

    app.include_router(pages)
    app.include_router(api.router(store))
    app.include_router(settings_api.router(store))
    app.include_router(training_api.router(store))
    app.include_router(strava_api.router(store, strava_transport))
    app.include_router(garmin_api.router(store, garmin_transport, garmin_pause))
    web.serve(app, web_dir or HERE / "web")
    return app


def _local(moment: dt.datetime, timezone: str, pattern: str = "%Y-%m-%d %H:%M") -> str:
    return moment.astimezone(ZoneInfo(timezone)).strftime(pattern)


def _lap_rows(laps: tuple[Lap, ...]) -> list[dict[str, Any]]:
    return [
        {
            "number": number,
            "elapsed_s": lap.elapsed_s,
            "distance_m": lap.distance_m,
            "pace_s_per_km": lap.pace_s_per_km,
        }
        for number, lap in enumerate(api.unless_single(laps), start=1)
    ]

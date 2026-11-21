import contextlib
import datetime as dt
import secrets
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo

import httpx2
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from makerundev import ActivityFileError, Lap, format
from makerundev.metrics import best_efforts, splits, summarize, time_in_zones

from makerundev_server import charts, config, garmin
from makerundev_server.db import ActivityRow, connect
from makerundev_server.garmin_sync import GarminSync
from makerundev_server.settings import FORM_FIELDS, ZONE_FIELDS, form_values, parse_form, timezones
from makerundev_server.store import Store
from makerundev_server.strava import ACTIVITY_URL, SCOPE, StravaClient, StravaError, credentials
from makerundev_server.sync import StravaSync
from makerundev_server.training import DEFAULT_RANGE, RANGES, load_view, today_in

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
HERE = Path(__file__).parent
STRAVA_NOTICES = {
    "connected": "Connected to Strava. Start a sync to bring your activities in.",
    "denied": "Strava access was not granted, so nothing was connected.",
    "state": "That Strava response did not match a connection started here. Try again.",
    "scope": "makerundev needs permission to read your activities, private ones included."
    " Connect again and leave that box ticked.",
    "failed": "Strava did not complete the connection. Check the client id and secret.",
    "disconnected": "Disconnected from Strava.",
}
GARMIN_NOTICES = {
    "saved": "Key saved. Start a sync to bring your activities in.",
    "empty": "Paste your Personal API key first.",
    "rejected": "Garmin did not accept that key. Check it was copied whole and has not expired.",
    "unreachable": "Garmin could not be reached to check the key. Try again later.",
    "removed": "Key removed. Activities imported from Garmin stay.",
}


def create_app(
    data_dir: Path | None = None,
    strava_transport: httpx2.BaseTransport | None = None,
    garmin_transport: httpx2.BaseTransport | None = None,
    garmin_pause: float = garmin.PAUSE_S,
) -> FastAPI:
    root = data_dir or config.data_dir()
    root.mkdir(parents=True, exist_ok=True)
    store = Store(root, connect(root))
    store.reset_syncs()
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.filters.update(
        km=format.kilometres,
        duration=format.duration,
        pace=format.pace,
        distance_name=format.distance_name,
        signed=_signed,
        local=_local,
    )
    templates.env.globals.update(
        format_pace=format.pace,
        format_bpm=lambda value: f"{value:.0f} bpm",
        format_metres=lambda value: f"{value:.0f} m",
    )

    def timezone() -> str:
        settings = store.athlete_settings()
        return settings.timezone if settings else "UTC"

    app = FastAPI(title="makerundev")
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    def index(request: Request, notices: list[str], status_code: int = 200) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"activities": store.list(), "notices": notices, "timezone": timezone()},
            status_code=status_code,
        )

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        return index(request, [])

    @app.post("/activities", response_class=HTMLResponse)
    def upload(request: Request, files: Annotated[list[UploadFile], File()]) -> HTMLResponse:
        notices: list[str] = []
        imported = 0
        for upload in files:
            name = upload.filename or "upload"
            data = upload.file.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                notices.append(f"{name}: larger than 64 MB")
                continue
            try:
                result = store.import_file(name, data)
            except ActivityFileError as error:
                notices.append(f"{name}: {error}")
                continue
            imported += 1
            if not result.created:
                notices.append(f"{name}: already imported")
        return index(request, notices, status_code=200 if imported else 400)

    @app.get("/activities/{activity_id}", response_class=HTMLResponse)
    def detail(request: Request, activity_id: int) -> HTMLResponse:
        row = _row(store, activity_id)
        activity = store.activity(row)
        records = activity.records
        summary = summarize(activity)
        settings = store.athlete_settings()
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
                "efforts": best_efforts(activity),
                "splits": _unless_single(splits(activity)),
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

    def settings_page(
        request: Request,
        values: dict[str, str],
        errors: dict[str, str],
        notice: str | None = None,
        status_code: int = 200,
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "values": values,
                "errors": errors,
                "notice": notice,
                "zone_fields": ZONE_FIELDS,
                "timezones": sorted(timezones()),
                "highest_heart_rate": store.highest_heart_rate(),
            },
            status_code=status_code,
        )

    @app.get("/settings", response_class=HTMLResponse)
    def settings(request: Request, recomputed: str = "", unreadable: str = "") -> HTMLResponse:
        notice = None
        if recomputed.isdigit():
            notice = "Settings saved." + _count(" TRIMP recomputed for {}.", int(recomputed))
            if unreadable.isdigit():
                notice += _count(" {} could not be read; see the server log.", int(unreadable))
        return settings_page(request, form_values(store.athlete_settings()), {}, notice)

    @app.post("/settings", response_class=HTMLResponse, response_model=None)
    async def save_settings(request: Request) -> Response:
        form = await request.form()
        values = {name: str(form.get(name, "")) for name in FORM_FIELDS}
        parsed, errors = parse_form(values)
        if parsed is None:
            return settings_page(request, values, errors, status_code=422)
        result = await run_in_threadpool(store.save_athlete_settings, parsed)
        query = f"recomputed={result.recomputed}&unreadable={result.unreadable}"
        return RedirectResponse(f"/settings?{query}", status_code=303)

    @app.get("/load", response_class=HTMLResponse)
    def load(request: Request, days: str = DEFAULT_RANGE) -> HTMLResponse:
        selected = days if days in RANGES else DEFAULT_RANGE
        settings = store.athlete_settings()
        view = None
        if settings is not None:
            today = today_in(settings.timezone)
            view = load_view(store.list(), settings.timezone, today, RANGES[selected])
        return templates.TemplateResponse(
            request,
            "load.html",
            {
                "settings_set": settings is not None,
                "view": view,
                "plot": charts.load_chart(view.days) if view else None,
                "ranges": RANGES,
                "selected": selected,
                "chart": {"width": charts.WIDTH, "height": charts.HEIGHT},
            },
        )

    def strava_client() -> StravaClient | None:
        configured = credentials()
        return StravaClient(configured, strava_transport) if configured else None

    def to_strava(notice: str = "") -> RedirectResponse:
        return RedirectResponse(f"/strava?notice={notice}" if notice else "/strava", 303)

    @app.get("/strava", response_class=HTMLResponse)
    def strava(request: Request, notice: str = "") -> HTMLResponse:
        connection = store.strava_connection()
        return templates.TemplateResponse(
            request,
            "strava.html",
            {
                "configured": credentials() is not None,
                "connected": connection is not None and connection.access_token is not None,
                "connection": connection,
                "notice": STRAVA_NOTICES.get(notice),
                "callback_domain": request.url.hostname,
                "timezone": timezone(),
            },
        )

    @app.post("/strava/connect", response_model=None)
    def strava_connect(request: Request) -> Response:
        client = strava_client()
        if client is None:
            return to_strava()
        state = secrets.token_urlsafe(32)
        store.begin_strava_oauth(state)
        redirect_uri = str(request.url_for("strava_callback"))
        return RedirectResponse(client.authorize_url(redirect_uri, state), status_code=303)

    @app.get("/strava/callback", name="strava_callback", response_model=None)
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

    @app.post("/strava/sync", response_model=None)
    def strava_sync() -> Response:
        client = strava_client()
        if client is not None and store.start_strava_sync():
            worker = threading.Thread(target=StravaSync(store, client).run, daemon=True)
            app.state.strava_sync = worker
            worker.start()
        return to_strava()

    @app.post("/strava/disconnect", response_model=None)
    def strava_disconnect() -> Response:
        client = strava_client()
        if client is not None:
            with contextlib.suppress(StravaError, httpx2.HTTPError, KeyError):
                client.revoke(StravaSync(store, client).access_token())
        store.disconnect_strava()
        return to_strava("disconnected")

    def garmin_client() -> garmin.GarminClient:
        return garmin.GarminClient(garmin_transport, pause=garmin_pause)

    def to_garmin(notice: str = "") -> RedirectResponse:
        return RedirectResponse(f"/garmin?notice={notice}" if notice else "/garmin", 303)

    @app.get("/garmin", response_class=HTMLResponse)
    def garmin_page(request: Request, notice: str = "") -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "garmin.html",
            {
                "connection": store.garmin.connection(),
                "notice": GARMIN_NOTICES.get(notice),
                "activity_url": garmin.ACTIVITY_URL,
                "timezone": timezone(),
            },
        )

    @app.post("/garmin/key", response_model=None)
    async def garmin_key(request: Request) -> Response:
        key = str((await request.form()).get("key", "")).strip()
        if not key:
            return to_garmin("empty")
        try:
            token = await run_in_threadpool(garmin_client().token, key)
        except garmin.Unauthorized:
            return to_garmin("rejected")
        except (garmin.GarminError, httpx2.HTTPError):
            return to_garmin("unreachable")
        await run_in_threadpool(store.garmin.save_key, key, token)
        return to_garmin("saved")

    @app.post("/garmin/sync", response_model=None)
    def garmin_sync() -> Response:
        running = getattr(app.state, "garmin_sync", None)
        if running is not None and running.is_alive():
            return to_garmin()
        if store.garmin.start_sync():
            worker = threading.Thread(target=GarminSync(store, garmin_client()).run, daemon=True)
            app.state.garmin_sync = worker
            worker.start()
        return to_garmin()

    @app.post("/garmin/remove", response_model=None)
    def garmin_remove() -> Response:
        store.garmin.remove_key()
        return to_garmin("removed")

    @app.get("/api/activities")
    def api_activities() -> list[dict[str, Any]]:
        return [_as_dict(row) for row in store.list()]

    @app.get("/api/activities/{activity_id}/records")
    def api_records(activity_id: int) -> list[dict[str, Any]]:
        return store.records(_row(store, activity_id)).to_dicts()

    return app


def _local(moment: dt.datetime, timezone: str, pattern: str = "%Y-%m-%d %H:%M") -> str:
    return moment.astimezone(ZoneInfo(timezone)).strftime(pattern)


def _signed(value: float) -> str:
    rounded = round(value)
    return f"{rounded:+d}" if rounded else "0"


def _count(template: str, count: int) -> str:
    if not count:
        return ""
    return template.format(f"{count} {'activity' if count == 1 else 'activities'}")


def _unless_single[T](rows: Sequence[T]) -> list[T]:
    return list(rows) if len(rows) >= 2 else []


def _lap_rows(laps: tuple[Lap, ...]) -> list[dict[str, Any]]:
    return [
        {
            "number": number,
            "elapsed_s": lap.elapsed_s,
            "distance_m": lap.distance_m,
            "pace_s_per_km": lap.elapsed_s / lap.distance_m * 1000
            if lap.elapsed_s is not None and lap.distance_m
            else None,
        }
        for number, lap in enumerate(_unless_single(laps), start=1)
    ]


def _row(store: Store, activity_id: int) -> ActivityRow:
    row = store.get(activity_id)
    if row is None:
        raise HTTPException(status_code=404, detail="activity not found")
    return row


def _as_dict(row: ActivityRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "filename": row.filename,
        "sport": row.sport,
        "device": row.device,
        "source_format": row.source_format,
        "start_time": row.start_time.isoformat(),
        "distance_m": row.distance_m,
        "elapsed_s": row.elapsed_s,
        "moving_s": row.moving_s,
        "pace_s_per_km": row.pace_s_per_km,
        "avg_heart_rate": row.avg_heart_rate,
        "max_heart_rate": row.max_heart_rate,
        "elevation_gain_m": row.elevation_gain_m,
        "trimp": row.trimp,
        "external_source": row.external_source,
        "external_id": row.external_id,
    }

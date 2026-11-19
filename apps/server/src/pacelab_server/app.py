import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pacelab import ActivityFileError, format
from pacelab.metrics import best_efforts

from pacelab_server import charts
from pacelab_server.db import ActivityRow, connect
from pacelab_server.settings import FORM_FIELDS, ZONE_FIELDS, form_values, parse_form, timezones
from pacelab_server.store import Store

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
HERE = Path(__file__).parent


def create_app(data_dir: Path | None = None) -> FastAPI:
    root = data_dir or Path(os.environ.get("PACELAB_DATA_DIR", "data"))
    root.mkdir(parents=True, exist_ok=True)
    store = Store(root, connect(root))
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.filters.update(
        km=format.kilometres,
        duration=format.duration,
        pace=format.pace,
        distance_name=format.distance_name,
    )
    templates.env.globals.update(
        format_pace=format.pace,
        format_bpm=lambda value: f"{value:.0f} bpm",
        format_metres=lambda value: f"{value:.0f} m",
    )

    app = FastAPI(title="pacelab")
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    def index(request: Request, notices: list[str], status_code: int = 200) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"activities": store.list(), "notices": notices},
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
        return templates.TemplateResponse(
            request,
            "activity.html",
            {
                "activity": row,
                "efforts": best_efforts(activity),
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

    @app.get("/api/activities")
    def api_activities() -> list[dict[str, Any]]:
        return [_as_dict(row) for row in store.list()]

    @app.get("/api/activities/{activity_id}/records")
    def api_records(activity_id: int) -> list[dict[str, Any]]:
        return store.records(_row(store, activity_id)).to_dicts()

    return app


def _count(template: str, count: int) -> str:
    if not count:
        return ""
    return template.format(f"{count} {'activity' if count == 1 else 'activities'}")


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
    }

import secrets
from pathlib import Path

import httpx2
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from makerundev_server import (
    api,
    config,
    garmin,
    garmin_api,
    map_source_api,
    settings_api,
    strava_api,
    training_api,
    web,
)
from makerundev_server.cross_site import CrossSiteGuard
from makerundev_server.db import connect
from makerundev_server.store import Store
from makerundev_server.strava import SCOPE, StravaClient
from makerundev_server.sync_errors import SyncError
from makerundev_server.training_load import Clock, TrainingLoad, system_clock

HERE = Path(__file__).parent


def create_app(
    data_dir: Path | None = None,
    strava_transport: httpx2.BaseTransport | None = None,
    garmin_transport: httpx2.BaseTransport | None = None,
    garmin_pause: float = garmin.PAUSE_S,
    web_dir: Path | None = None,
    clock: Clock = system_clock,
) -> FastAPI:
    root = data_dir or config.data_dir()
    root.mkdir(parents=True, exist_ok=True)
    store = Store(root, connect(root))
    store.reset_syncs()
    store.catch_up()

    app = FastAPI(title="makerundev", version="pre-1.0")
    pages = APIRouter(include_in_schema=False)
    app.add_middleware(CrossSiteGuard)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

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
        except (SyncError, httpx2.HTTPError, KeyError):
            return to_strava("failed")
        store.save_strava_tokens(tokens)
        return to_strava("connected")

    app.include_router(pages)
    app.include_router(api.router(store))
    app.include_router(settings_api.router(store))
    app.include_router(training_api.router(TrainingLoad(store, clock)))
    app.include_router(strava_api.router(store, strava_transport))
    app.include_router(garmin_api.router(store, garmin_transport, garmin_pause))
    app.include_router(map_source_api.router(store, root))
    app.include_router(map_source_api.tiles(root))
    web.serve(app, web_dir or HERE / "web")
    return app

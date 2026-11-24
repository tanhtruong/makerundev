import contextlib
from typing import Any, TypeGuard

import httpx2
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from makerundev_server.api import Problem, operation_id
from makerundev_server.db import StravaConnectionRow
from makerundev_server.store import Store
from makerundev_server.strava import ACTIVITY_URL, StravaClient, StravaError, credentials
from makerundev_server.sync import StravaSync
from makerundev_server.sync_api import SyncStatus, run_in_background, sync_status


class StravaStatus(BaseModel):
    configured: bool
    connected: bool
    callback_domain: str
    sync: SyncStatus | None


class StravaDisconnected(BaseModel):
    removed_activities: int


def strava_client(transport: httpx2.BaseTransport | None) -> StravaClient | None:
    configured = credentials()
    return StravaClient(configured, transport) if configured else None


def is_connected(connection: StravaConnectionRow | None) -> TypeGuard[StravaConnectionRow]:
    return connection is not None and connection.access_token is not None


def begin_sync(app: FastAPI, store: Store, client: StravaClient) -> None:
    run_in_background(app, "strava_sync", store.start_strava_sync, StravaSync(store, client).run)


def disconnect(store: Store, client: StravaClient | None) -> int:
    if client is not None:
        with contextlib.suppress(StravaError, httpx2.HTTPError, KeyError):
            client.revoke(StravaSync(store, client).access_token())
    return store.disconnect_strava()


def router(store: Store, transport: httpx2.BaseTransport | None) -> APIRouter:
    api = APIRouter(prefix="/api", generate_unique_id_function=operation_id)
    refused: dict[int | str, dict[str, Any]] = {
        409: {"model": Problem, "description": "Strava is not configured or not connected"}
    }

    def status(request: Request) -> StravaStatus:
        connection = store.strava_connection()
        return StravaStatus(
            configured=credentials() is not None,
            connected=is_connected(connection),
            callback_domain=request.url.hostname or "",
            sync=sync_status(connection, ACTIVITY_URL) if is_connected(connection) else None,
        )

    @api.get("/strava", tags=["strava"])
    def strava_status(request: Request, response: Response) -> StravaStatus:
        response.headers["Cache-Control"] = "no-store"
        return status(request)

    @api.post("/strava/sync", tags=["strava"], status_code=202, responses=refused)
    def start_strava_sync(request: Request) -> StravaStatus:
        client = strava_client(transport)
        if client is None:
            raise HTTPException(status_code=409, detail="strava is not configured")
        if not is_connected(store.strava_connection()):
            raise HTTPException(status_code=409, detail="strava is not connected")
        begin_sync(request.app, store, client)
        return status(request)

    @api.delete("/strava", tags=["strava"])
    def disconnect_strava() -> StravaDisconnected:
        return StravaDisconnected(removed_activities=disconnect(store, strava_client(transport)))

    return api

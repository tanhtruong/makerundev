from typing import Any, Literal

import httpx2
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from makerundev_server import garmin
from makerundev_server.api import Problem, operation_id
from makerundev_server.garmin_sync import GarminSync
from makerundev_server.store import Store
from makerundev_server.sync_api import SyncStatus, run_in_background, sync_status

KeyCheck = Literal["saved", "empty", "rejected", "unreachable"]

KEY_ERRORS: dict[str, str] = {
    "empty": "Paste your Personal API key first.",
    "rejected": "Garmin did not accept that key. Check it was copied whole and has not expired.",
}


class GarminStatus(BaseModel):
    key_saved: bool
    sync: SyncStatus | None


class GarminKey(BaseModel):
    key: str


def save_key(store: Store, client: garmin.GarminClient, key: str) -> KeyCheck:
    key = key.strip()
    if not key:
        return "empty"
    try:
        token = client.token(key)
    except garmin.Unauthorized:
        return "rejected"
    except (garmin.GarminError, httpx2.HTTPError):
        return "unreachable"
    store.garmin.save_key(key, token)
    return "saved"


def begin_sync(app: FastAPI, store: Store, client: garmin.GarminClient) -> None:
    run_in_background(app, "garmin_sync", store.garmin.start_sync, GarminSync(store, client).run)


def router(store: Store, transport: httpx2.BaseTransport | None, pause: float) -> APIRouter:
    api = APIRouter(prefix="/api", generate_unique_id_function=operation_id)

    def client() -> garmin.GarminClient:
        return garmin.GarminClient(transport, pause=pause)

    def status() -> GarminStatus:
        connection = store.garmin.connection()
        return GarminStatus(
            key_saved=connection is not None,
            sync=sync_status(connection, garmin.ACTIVITY_URL) if connection else None,
        )

    @api.get("/garmin", tags=["garmin"])
    def garmin_status(response: Response) -> GarminStatus:
        response.headers["Cache-Control"] = "no-store"
        return status()

    unreachable: dict[int | str, dict[str, Any]] = {
        502: {"model": Problem, "description": "Garmin could not be reached to check the key"}
    }

    @api.put("/garmin/key", tags=["garmin"], responses=unreachable)
    def save_garmin_key(chosen: GarminKey) -> GarminStatus:
        checked = save_key(store, client(), chosen.key)
        if checked == "unreachable":
            raise HTTPException(status_code=502, detail="garmin could not be reached")
        if checked != "saved":
            raise RequestValidationError(
                [{"type": "value_error", "loc": ("body", "key"), "msg": KEY_ERRORS[checked]}]
            )
        return status()

    refused: dict[int | str, dict[str, Any]] = {
        409: {"model": Problem, "description": "No Garmin key is saved"}
    }

    @api.post("/garmin/sync", tags=["garmin"], status_code=202, responses=refused)
    def start_garmin_sync(request: Request) -> GarminStatus:
        if store.garmin.connection() is None:
            raise HTTPException(status_code=409, detail="garmin key is not saved")
        begin_sync(request.app, store, client())
        return status()

    @api.delete("/garmin/key", tags=["garmin"])
    def remove_garmin_key() -> GarminStatus:
        store.garmin.remove_key()
        return status()

    return api

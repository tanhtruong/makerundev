from dataclasses import asdict

from fastapi import APIRouter, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from makerundev_server import map_source
from makerundev_server.api import operation_id
from makerundev_server.map_source import MapKind, Rendering
from makerundev_server.store import Store


class MapSource(BaseModel):
    kind: MapKind
    rendering: Rendering
    url: str
    dark_url: str | None
    attribution: str
    provider: str
    terms_url: str | None
    privacy_url: str | None


class MapSourceView(BaseModel):
    source: MapSource | None
    presets: list[MapSource]


class MapSourceChoice(BaseModel):
    kind: MapKind
    url: str | None
    attribution: str | None


def router(store: Store) -> APIRouter:
    api = APIRouter(prefix="/api", generate_unique_id_function=operation_id)

    def view(response: Response) -> MapSourceView:
        response.headers["Cache-Control"] = "no-store"
        source = store.map_source.source()
        return MapSourceView(
            source=MapSource(**asdict(source)) if source else None,
            presets=[MapSource(**asdict(preset)) for preset in map_source.PRESETS.values()],
        )

    @api.get("/map-source", tags=["map"])
    def get_map_source(response: Response) -> MapSourceView:
        return view(response)

    @api.put("/map-source", tags=["map"])
    def save_map_source(chosen: MapSourceChoice, response: Response) -> MapSourceView:
        errors = map_source.rule_errors(chosen.kind, chosen.url, chosen.attribution)
        if errors:
            raise RequestValidationError(
                [
                    {"type": "value_error", "loc": ("body", field), "msg": message}
                    for field, message in errors.items()
                ]
            )
        custom = chosen.kind not in map_source.PRESETS
        store.map_source.save(
            chosen.kind,
            chosen.url if custom else None,
            chosen.attribution.strip() if custom and chosen.attribution else None,
        )
        return view(response)

    @api.delete("/map-source", tags=["map"])
    def remove_map_source(response: Response) -> MapSourceView:
        store.map_source.remove()
        return view(response)

    return api

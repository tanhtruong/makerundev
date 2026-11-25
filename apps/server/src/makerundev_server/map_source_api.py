from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from pydantic import BaseModel

from makerundev_server import map_source
from makerundev_server.api import operation_id
from makerundev_server.map_source import MapKind, Rendering, ResolvedSource, TileFile
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
    file: str | None
    file_missing: bool


class MapTileFile(BaseModel):
    name: str
    size_bytes: int


class MapSourceView(BaseModel):
    source: MapSource | None
    presets: list[MapSource]
    files: list[MapTileFile]


class MapSourceChoice(BaseModel):
    kind: MapKind
    url: str | None
    attribution: str | None
    file: str | None = None


def described(source: ResolvedSource, files: list[TileFile]) -> MapSource:
    missing = source.file is not None and source.file not in {file.name for file in files}
    return MapSource(**asdict(source), file_missing=missing)


def router(store: Store, data_dir: Path) -> APIRouter:
    api = APIRouter(prefix="/api", generate_unique_id_function=operation_id)

    def view(response: Response) -> MapSourceView:
        response.headers["Cache-Control"] = "no-store"
        source = store.map_source.source()
        files = map_source.tile_files(data_dir)
        return MapSourceView(
            source=described(source, files) if source else None,
            presets=[described(preset, files) for preset in map_source.PRESETS.values()],
            files=[MapTileFile(**asdict(file)) for file in files],
        )

    @api.get("/map-source", tags=["map"])
    def get_map_source(response: Response) -> MapSourceView:
        return view(response)

    @api.put("/map-source", tags=["map"])
    def save_map_source(chosen: MapSourceChoice, response: Response) -> MapSourceView:
        errors = map_source.rule_errors(
            chosen.kind,
            chosen.url,
            chosen.attribution,
            chosen.file,
            map_source.tile_files(data_dir),
        )
        if errors:
            raise RequestValidationError(
                [
                    {"type": "value_error", "loc": ("body", field), "msg": message}
                    for field, message in errors.items()
                ]
            )
        if chosen.kind == "pmtiles":
            store.map_source.save(chosen.kind, chosen.file, None)
            return view(response)
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


def tiles(data_dir: Path) -> APIRouter:
    routes = APIRouter(include_in_schema=False)

    @routes.get("/tiles/{name:path}", response_model=None)
    def tile_file(name: str) -> FileResponse:
        if name not in {file.name for file in map_source.tile_files(data_dir)}:
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(data_dir / name, headers={"Cache-Control": "no-cache"})

    return routes

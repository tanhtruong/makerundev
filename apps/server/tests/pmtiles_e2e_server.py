from fastapi import FastAPI
from makerundev_server import config, create_app
from pmtiles_file import write_pmtiles


def create() -> FastAPI:
    root = config.data_dir()
    root.mkdir(parents=True, exist_ok=True)
    write_pmtiles(root / "harbour.pmtiles")
    return create_app()

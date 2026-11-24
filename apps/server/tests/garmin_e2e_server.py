import importlib.util
import threading
from pathlib import Path
from types import ModuleType

import httpx2
from fastapi import FastAPI
from garmin_fake import FakeGarmin, listing
from makerundev_server import create_app

ROOT_CONFTEST = Path(__file__).resolve().parents[3] / "conftest.py"


def fit_fixtures() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fit_fixtures", ROOT_CONFTEST)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create() -> FastAPI:
    fixtures = fit_fixtures()
    fake = FakeGarmin(fixtures.build_fit, fixtures.build_zip)
    fake.run(1, 1)
    fake.run(2, 2)
    fake.listed.append(listing(3, 3, manualActivity=True, startTimeGMT="2026-03-04 03:00:00"))
    released = threading.Event()
    fake.after_download = {"2": lambda: released.wait(timeout=60)}
    app = create_app(garmin_transport=httpx2.MockTransport(fake), garmin_pause=0.0)

    @app.post("/e2e/garmin/release", include_in_schema=False)
    def release() -> None:
        released.set()

    return app

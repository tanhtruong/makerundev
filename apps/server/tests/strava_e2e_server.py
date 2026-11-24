import threading

import httpx2
from fastapi import FastAPI
from makerundev_server import create_app
from strava_fake import FakeStrava, summary


def create() -> FastAPI:
    fake = FakeStrava([summary(1, 1), summary(2, 2, manual=True)])
    released = threading.Event()

    def strava(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/streams"):
            released.wait(timeout=60)
        return fake(request)

    app = create_app(strava_transport=httpx2.MockTransport(strava))

    @app.post("/e2e/strava/release", include_in_schema=False)
    def release() -> None:
        released.set()

    return app

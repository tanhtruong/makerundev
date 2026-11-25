import base64
import datetime as dt
import json
from collections.abc import Callable

import httpx2
from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.db import connect
from makerundev_server.garmin import GarminClient
from makerundev_server.garmin_sync import garmin_sync
from makerundev_server.store import Store

KEY = "personal-api-key-0123456789"


def run_start(day: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, 3, day, 7, minute, tzinfo=dt.UTC)


def listing(activity_id: int, day: int, minute: int = 0, distance: float = 3000.0, **fields):
    return {
        "activityId": activity_id,
        "activityName": f"Run {activity_id}",
        "activityType": {"typeKey": "running"},
        "startTimeGMT": run_start(day, minute).strftime("%Y-%m-%d %H:%M:%S"),
        "distance": distance,
        "manualActivity": False,
    } | fields


def jwt(issued_at: dt.datetime, expires_at: dt.datetime) -> str:
    def part(value: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    claims = {"iat": int(issued_at.timestamp()), "exp": int(expires_at.timestamp())}
    return f"{part({'alg': 'RS256'})}.{part(claims)}.signature"


class FakeGarmin:
    def __init__(self, make_fit, make_zip):
        self.make_fit = make_fit
        self.make_zip = make_zip
        self.key = KEY
        self.listed: list[dict] = []
        self.files: dict[str, bytes] = {}
        self.tokens: set[str] = set()
        self.tokens_issued = 0
        self.downloads: list[str] = []
        self.searches = 0
        self.data_requests = 0
        self.throttle_after: int | None = None
        self.after_download: dict[str, Callable[[], object]] = {}

    def run(
        self,
        activity_id: int,
        day: int,
        entry_name: str | None = None,
        minute: int = 0,
        step: float = 3.0,
        **fields,
    ):
        self.listed.append(listing(activity_id, day, minute, step * 1000, **fields))
        self.files[str(activity_id)] = self.make_zip(
            (entry_name or f"{activity_id}_ACTIVITY.fit", self.fit(day, minute=minute, step=step))
        )

    def delete(self, activity_id: str) -> None:
        self.listed = [a for a in self.listed if str(a["activityId"]) != activity_id]
        self.files.pop(activity_id, None)

    def fit(self, day: int, heart_rate: int = 140, minute: int = 0, step: float = 3.0) -> bytes:
        rows = [{"t": float(i), "distance": i * step, "hr": heart_rate} for i in range(1001)]
        return self.make_fit(rows, start=run_start(day, minute))

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        authorization = request.headers.get("Authorization", "")
        if path == "/personalapitoken-service/personal-api/personal-api-key/token":
            if request.method != "POST" or authorization != f"ApiKey {self.key}":
                return httpx2.Response(401, text="Unauthorized")
            self.tokens_issued += 1
            now = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=self.tokens_issued)
            token = jwt(now, now + dt.timedelta(hours=24))
            self.tokens.add(token)
            return httpx2.Response(200, text=token, headers={"Content-Type": "text/plain"})
        if authorization.removeprefix("Bearer ") not in self.tokens:
            return httpx2.Response(401, text="Unauthorized")
        self.data_requests += 1
        if self.throttle_after is not None and self.data_requests > self.throttle_after:
            return httpx2.Response(429, headers={"Retry-After": "120"})
        if path == "/activitylist-service/activities/search/activities":
            return self.search(request.url.params)
        activity_id = path.rsplit("/", 1)[1]
        assert path == f"/download-service/files/activity/{activity_id}"
        self.downloads.append(activity_id)
        if activity_id in self.after_download:
            self.after_download[activity_id]()
        if activity_id not in self.files:
            return httpx2.Response(404, text="Not Found")
        return httpx2.Response(
            200,
            content=self.files[activity_id],
            headers={"Content-Type": "application/x-zip-compressed"},
        )

    def search(self, params) -> httpx2.Response:
        self.searches += 1
        first = int(params["start"])
        size = int(params["limit"])
        since = params.get("startDate", "")
        until = params.get("endDate", "9999")
        within = [a for a in self.listed if since <= a.get("startTimeGMT", "")[:10] <= until]
        newest_first = sorted(within, key=lambda a: a.get("startTimeGMT", ""), reverse=True)
        return httpx2.Response(200, json=newest_first[first : first + size])


def app_with(tmp_path, fake) -> tuple[TestClient, Store]:
    app = create_app(
        data_dir=tmp_path, garmin_transport=httpx2.MockTransport(fake), garmin_pause=0.0
    )
    return TestClient(app), Store(tmp_path, connect(tmp_path))


def save_key(client, key=KEY):
    return client.put("/api/garmin/key", json={"key": key})


def sync(store, fake) -> str:
    assert store.garmin_state.start()
    garmin_sync(store, GarminClient(httpx2.MockTransport(fake), pause=0.0)).run()
    connection = store.garmin.connection()
    assert connection is not None and not connection.syncing
    return connection.sync_outcome

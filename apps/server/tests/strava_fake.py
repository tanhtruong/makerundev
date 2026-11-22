import datetime as dt
from urllib.parse import parse_qs

import httpx2
from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.db import connect
from makerundev_server.store import Store
from makerundev_server.strava import Credentials, StravaClient, Tokens
from makerundev_server.sync import StravaSync

FIT_START = dt.datetime(2026, 3, 1, 7, 0, tzinfo=dt.UTC)
FAR = dt.datetime(2100, 1, 1, tzinfo=dt.UTC)


def summary(strava_id: int, day: int, distance: float = 3000.0, **fields):
    start = dt.datetime(2026, 3, day, 7, 0, tzinfo=dt.UTC)
    return {
        "id": strava_id,
        "name": f"Run {strava_id}",
        "sport_type": "Run",
        "trainer": False,
        "manual": False,
        "distance": distance,
        "start_date": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
    } | fields


def streams(seconds: int = 1001):
    data = {
        "time": list(range(seconds)),
        "latlng": [[55.67 + i * 0.00003, 12.56] for i in range(seconds)],
        "distance": [i * 3.0 for i in range(seconds)],
        "heartrate": [140] * seconds,
        "cadence": [85] * seconds,
    }
    return {key: {"data": values, "resolution": "high"} for key, values in data.items()}


class FakeStrava:
    def __init__(self, activities, without_streams=(), limit=(100, 1000)):
        self.activities = list(activities)
        self.without_streams = {str(i) for i in without_streams}
        self.limit = limit
        self.usage = [0, 0]
        self.requests: list[str] = []
        self.revoked: list[str] = []
        self.revoke_fails = False
        self.token_grants: list[dict[str, str]] = []
        self.broken_streams: dict[str, dict] = {}
        self.refused: set[str] = set()
        self.laps: dict[str, list[dict]] = {}
        self.without_detail: set[str] = set()
        self.throttled_detail: set[str] = set()

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path == "/oauth/token":
            grant = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
            self.token_grants.append(grant)
            if grant.get("code") == "bad":
                return httpx2.Response(400, json={"message": "Bad Request"})
            number = len(self.token_grants)
            return httpx2.Response(
                200,
                json={
                    "access_token": f"access-{number}",
                    "refresh_token": f"refresh-{number}",
                    "expires_at": int(FAR.timestamp()),
                },
            )
        if path == "/oauth/revoke":
            if self.revoke_fails:
                return httpx2.Response(500)
            self.revoked.append(parse_qs(request.content.decode())["token"][0])
            return httpx2.Response(200)
        self.requests.append(path.removeprefix("/api/v3"))
        if self.usage[0] >= self.limit[0] or self.usage[1] >= self.limit[1]:
            return httpx2.Response(
                429, json={"message": "Rate Limit Exceeded"}, headers=self.rate()
            )
        self.usage = [self.usage[0] + 1, self.usage[1] + 1]
        if path == "/api/v3/athlete/activities":
            return httpx2.Response(200, json=self.listed(request.url.params), headers=self.rate())
        strava_id = path.split("/")[4]
        if strava_id in self.refused:
            return httpx2.Response(403, json={"message": "Forbidden"}, headers=self.rate())
        if path.endswith(f"/activities/{strava_id}"):
            return self.detail(strava_id)
        if strava_id in self.without_streams:
            return httpx2.Response(404, json={"message": "Not Found"}, headers=self.rate())
        body = self.broken_streams.get(strava_id, streams())
        return httpx2.Response(200, json=body, headers=self.rate())

    def detail(self, strava_id: str) -> httpx2.Response:
        found = [a for a in self.activities if str(a["id"]) == strava_id]
        if strava_id in self.throttled_detail:
            return httpx2.Response(
                429, json={"message": "Rate Limit Exceeded"}, headers=self.rate()
            )
        if strava_id in self.without_detail or not found:
            return httpx2.Response(404, json={"message": "Not Found"}, headers=self.rate())
        body = found[0] | {"laps": self.laps.get(strava_id, [])}
        return httpx2.Response(200, json=body, headers=self.rate())

    def rate(self) -> dict[str, str]:
        return {
            "X-ReadRateLimit-Limit": f"{self.limit[0]},{self.limit[1]}",
            "X-ReadRateLimit-Usage": f"{self.usage[0]},{self.usage[1]}",
        }

    def listed(self, params) -> list[dict]:
        def epoch(item) -> float:
            return dt.datetime.fromisoformat(item["start_date"]).timestamp()

        chosen = self.activities
        if "before" in params:
            chosen = [a for a in chosen if epoch(a) < int(params["before"])]
        if "after" in params:
            chosen = [a for a in chosen if epoch(a) > int(params["after"])]
        chosen = sorted(chosen, key=epoch, reverse="after" not in params)
        size = int(params["per_page"])
        first = (int(params["page"]) - 1) * size
        return chosen[first : first + size]

    def stream_requests(self) -> list[str]:
        return [path.split("/")[2] for path in self.requests if path.endswith("/streams")]

    def detail_requests(self) -> list[str]:
        return [
            path.split("/")[2]
            for path in self.requests
            if path.startswith("/activities/") and path.count("/") == 2
        ]


def lap(start: str, elapsed_time: float, distance: float) -> dict:
    return {"start_date": start, "elapsed_time": elapsed_time, "distance": distance}


def connected(tmp_path, fake, expires_at=FAR):
    app = create_app(data_dir=tmp_path, strava_transport=httpx2.MockTransport(fake))
    store = Store(tmp_path, connect(tmp_path))
    store.save_strava_tokens(Tokens("access-0", "refresh-0", expires_at))
    return TestClient(app), store


def sync(store, fake) -> str:
    assert store.start_strava_sync()
    client = StravaClient(Credentials("4242", "application-secret"), httpx2.MockTransport(fake))
    StravaSync(store, client).run()
    connection = store.strava_connection()
    assert connection is not None and not connection.syncing
    return connection.sync_message


def upload(client, name, data):
    return client.post("/activities", files=[("files", (name, data, "application/octet-stream"))])

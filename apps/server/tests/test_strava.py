import datetime as dt
import gzip
import json
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.db import connect
from makerundev_server.settings import AthleteSettings
from makerundev_server.store import Store, same_activity
from makerundev_server.strava import Credentials, StravaClient, Tokens
from makerundev_server.sync import PAUSED_DAILY, PAUSED_SHORT, REJECTED, UP_TO_DATE, StravaSync

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
        if strava_id in self.without_streams:
            return httpx2.Response(404, json={"message": "Not Found"}, headers=self.rate())
        body = self.broken_streams.get(strava_id, streams())
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


@pytest.fixture(autouse=True)
def strava_application(monkeypatch):
    monkeypatch.setenv("MAKERUNDEV_STRAVA_CLIENT_ID", "4242")
    monkeypatch.setenv("MAKERUNDEV_STRAVA_CLIENT_SECRET", "application-secret")


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


def test_first_sync_brings_in_every_activity_with_its_stream(tmp_path):
    fake = FakeStrava([summary(1, 1), summary(2, 2), summary(3, 3)])
    client, store = connected(tmp_path, fake)
    store.save_athlete_settings(AthleteSettings(max_hr=190, resting_hr=50))

    assert sync(store, fake) == UP_TO_DATE

    assert fake.stream_requests() == ["3", "2", "1"]
    activities = client.get("/api/activities").json()
    assert [(a["external_source"], a["external_id"]) for a in activities] == [
        ("strava", "3"),
        ("strava", "2"),
        ("strava", "1"),
    ]
    newest = activities[0]
    assert newest["filename"] == "Run 3"
    assert newest["source_format"] == "strava"
    assert newest["device"] is None
    assert newest["distance_m"] == 3000.0
    assert newest["start_time"] == "2026-03-03T07:00:00+00:00"
    assert newest["trimp"] > 0
    records = client.get(f"/api/activities/{newest['id']}/records").json()
    assert records[0]["cadence"] == 170.0
    page = client.get(f"/activities/{newest['id']}")
    assert 'href="https://www.strava.com/activities/3"' in page.text
    assert "View on Strava" in page.text
    original = json.loads(gzip.decompress((tmp_path / "originals" / "strava-3").read_bytes()))
    assert original["activity"]["id"] == 3
    connection = store.strava_connection()
    assert (connection.imported, connection.matched, connection.backfill_done) == (3, 0, True)


def test_a_later_sync_only_asks_for_what_is_new(tmp_path):
    fake = FakeStrava([summary(1, 1), summary(2, 2)])
    client, store = connected(tmp_path, fake)
    sync(store, fake)
    fake.activities.append(summary(3, 3))
    fake.requests.clear()

    assert sync(store, fake) == UP_TO_DATE

    assert fake.stream_requests() == ["3"]
    assert len(client.get("/api/activities").json()) == 3
    assert store.strava_connection().imported == 1


def test_sync_pauses_before_the_rate_limit_and_resumes_where_it_stopped(tmp_path):
    fake = FakeStrava([summary(i, i) for i in range(1, 9)], limit=(10, 1000))
    client, store = connected(tmp_path, fake)

    assert sync(store, fake) == PAUSED_SHORT

    assert fake.usage[0] == 6
    assert fake.stream_requests() == ["8", "7", "6", "5", "4"]
    assert store.strava_connection().backfill_done is False
    fake.usage = [0, fake.usage[1]]

    assert sync(store, fake) == UP_TO_DATE

    assert fake.stream_requests() == ["8", "7", "6", "5", "4", "3", "2", "1"]
    assert len(client.get("/api/activities").json()) == 8


def test_sync_pauses_for_the_day_when_the_daily_limit_is_close(tmp_path):
    fake = FakeStrava([summary(1, 1), summary(2, 2)], limit=(100, 21))
    _, store = connected(tmp_path, fake)

    assert sync(store, fake) == PAUSED_DAILY

    assert fake.stream_requests() == ["2"]


def test_a_429_from_strava_pauses_the_sync(tmp_path):
    fake = FakeStrava([summary(1, 1)])
    fake.usage = [100, 100]
    _, store = connected(tmp_path, fake)

    assert sync(store, fake) == PAUSED_SHORT


def test_activities_without_usable_streams_are_listed_and_not_tried_again(tmp_path):
    fake = FakeStrava(
        [summary(1, 1), summary(2, 2, manual=True), summary(3, 3), summary(4, 4)],
        without_streams=[3],
    )
    fake.broken_streams["4"] = {"time": {"data": []}}
    client, store = connected(tmp_path, fake)

    assert sync(store, fake) == UP_TO_DATE

    assert fake.stream_requests() == ["4", "3", "1"]
    assert [a["external_id"] for a in client.get("/api/activities").json()] == ["1"]
    skipped = {item["id"]: item["reason"] for item in store.strava_connection().skipped}
    assert skipped == {
        "2": "a manual entry, with no streams",
        "3": "no streams on Strava",
        "4": "the Strava activity has no time stream",
    }
    page = client.get("/strava").text
    assert "Skipped activities" in page and "Run 3" in page
    fake.requests.clear()

    sync(store, fake)

    assert fake.stream_requests() == []


def test_a_strava_activity_already_imported_from_a_file_is_matched_not_duplicated(
    tmp_path, steady_run_fit
):
    fake = FakeStrava([summary(77, 1, distance=3040.0)])
    client, store = connected(tmp_path, fake)
    upload(client, "morning.fit", steady_run_fit)

    assert sync(store, fake) == UP_TO_DATE

    assert fake.stream_requests() == []
    activities = client.get("/api/activities").json()
    assert [(a["filename"], a["source_format"], a["external_id"]) for a in activities] == [
        ("morning.fit", "fit", "77")
    ]
    assert store.strava_connection().matched == 1


def test_a_bulk_export_file_is_matched_by_the_strava_id_in_its_name(tmp_path, steady_run_fit):
    fake = FakeStrava([summary(77, 9, distance=9000.0)])
    client, store = connected(tmp_path, fake)
    upload(client, "77.fit.gz", gzip.compress(steady_run_fit))

    sync(store, fake)

    assert [a["external_id"] for a in client.get("/api/activities").json()] == ["77"]


def test_a_file_uploaded_after_a_sync_replaces_the_synced_stream(tmp_path, steady_run_fit):
    fake = FakeStrava([summary(77, 1)])
    client, store = connected(tmp_path, fake)
    sync(store, fake)
    synced = client.get("/api/activities").json()[0]
    assert (tmp_path / "streams" / "strava-77.parquet").exists()

    assert upload(client, "morning.fit", steady_run_fit).status_code == 200

    activities = client.get("/api/activities").json()
    assert len(activities) == 1
    replaced = activities[0]
    assert replaced["id"] == synced["id"]
    assert (replaced["filename"], replaced["source_format"], replaced["device"]) == (
        "morning.fit",
        "fit",
        "garmin fr965",
    )
    assert replaced["external_id"] == "77"
    assert not (tmp_path / "streams" / "strava-77.parquet").exists()
    assert not (tmp_path / "originals" / "strava-77").exists()
    records = client.get(f"/api/activities/{replaced['id']}/records").json()
    assert records[0]["power"] == 250.0
    assert upload(client, "again.fit", steady_run_fit).status_code == 200
    assert len(client.get("/api/activities").json()) == 1


@pytest.mark.parametrize(
    ("seconds_apart", "distance", "other_distance", "same"),
    [
        (0, 3000.0, 3000.0, True),
        (60, 3000.0, 3000.0, True),
        (61, 3000.0, 3000.0, False),
        (-60, 3000.0, 3200.0, True),
        (0, 3000.0, 3201.0, False),
        (0, 20000.0, 21000.0, True),
        (0, 20000.0, 21060.0, False),
    ],
)
def test_two_activities_are_the_same_within_a_minute_and_5_percent_or_200_m(
    seconds_apart, distance, other_distance, same
):
    other = FIT_START + dt.timedelta(seconds=seconds_apart)

    assert same_activity(FIT_START, distance, other, other_distance) is same


def test_disconnect_removes_what_came_only_from_strava_even_if_revoking_fails(
    tmp_path, steady_run_fit
):
    fake = FakeStrava([summary(77, 1), summary(78, 2)])
    fake.revoke_fails = True
    client, store = connected(tmp_path, fake)
    upload(client, "morning.fit", steady_run_fit)
    sync(store, fake)
    assert (tmp_path / "streams" / "strava-78.parquet").exists()

    response = client.post("/strava/disconnect", follow_redirects=False)

    assert response.headers["location"] == "/strava?notice=disconnected"
    activities = client.get("/api/activities").json()
    assert [(a["filename"], a["external_source"], a["external_id"]) for a in activities] == [
        ("morning.fit", None, None)
    ]
    assert not (tmp_path / "streams" / "strava-78.parquet").exists()
    assert not (tmp_path / "originals" / "strava-78").exists()
    assert store.strava_connection() is None
    assert "Connect with Strava" in client.get("/strava").text


def test_disconnect_revokes_the_token(tmp_path):
    fake = FakeStrava([])
    client, _ = connected(tmp_path, fake)

    client.post("/strava/disconnect")

    assert fake.revoked == ["access-0"]


def test_connecting_goes_through_strava_and_stores_the_tokens(tmp_path):
    fake = FakeStrava([])
    client = TestClient(create_app(data_dir=tmp_path, strava_transport=httpx2.MockTransport(fake)))
    store = Store(tmp_path, connect(tmp_path))

    redirect = client.post("/strava/connect", follow_redirects=False)

    target = urlsplit(redirect.headers["location"])
    query = {key: values[0] for key, values in parse_qs(target.query).items()}
    assert (target.netloc, target.path) == ("www.strava.com", "/oauth/authorize")
    assert query["client_id"] == "4242"
    assert query["redirect_uri"] == "http://testserver/strava/callback"
    assert query["scope"] == "activity:read_all"
    assert query["state"] == store.strava_connection().oauth_state

    callback = client.get(
        "/strava/callback",
        params={"code": "good", "scope": "read,activity:read_all", "state": query["state"]},
        follow_redirects=False,
    )

    assert callback.headers["location"] == "/strava?notice=connected"
    assert fake.token_grants[0]["client_secret"] == "application-secret"
    connection = store.strava_connection()
    assert (connection.access_token, connection.refresh_token) == ("access-1", "refresh-1")
    assert connection.oauth_state is None
    page = client.get("/strava?notice=connected").text
    assert "Sync now" in page and "Powered by Strava" in page
    assert "access-1" not in page and "refresh-1" not in page
    assert "application-secret" not in page


@pytest.mark.parametrize(
    ("params", "notice"),
    [
        ({"code": "good", "scope": "activity:read_all", "state": "forged"}, "state"),
        ({"code": "good", "scope": "activity:read_all", "state": ""}, "state"),
        ({"error": "access_denied", "state": "STATE"}, "denied"),
        ({"code": "good", "scope": "read", "state": "STATE"}, "scope"),
        ({"code": "bad", "scope": "activity:read_all", "state": "STATE"}, "failed"),
    ],
)
def test_a_callback_that_is_forged_denied_or_too_narrow_connects_nothing(tmp_path, params, notice):
    fake = FakeStrava([])
    client = TestClient(create_app(data_dir=tmp_path, strava_transport=httpx2.MockTransport(fake)))
    store = Store(tmp_path, connect(tmp_path))
    client.post("/strava/connect", follow_redirects=False)
    state = store.strava_connection().oauth_state
    sent = {key: state if value == "STATE" else value for key, value in params.items()}

    callback = client.get("/strava/callback", params=sent, follow_redirects=False)

    assert callback.headers["location"] == f"/strava?notice={notice}"
    assert store.strava_connection().access_token is None
    assert "Connect with Strava" in client.get(callback.headers["location"]).text


def test_an_access_token_about_to_expire_is_refreshed_and_the_new_pair_kept(tmp_path):
    fake = FakeStrava([summary(1, 1)])
    soon = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=30)
    _, store = connected(tmp_path, fake, expires_at=soon)

    assert sync(store, fake) == UP_TO_DATE

    assert fake.token_grants == [
        {
            "client_id": "4242",
            "client_secret": "application-secret",
            "grant_type": "refresh_token",
            "refresh_token": "refresh-0",
        }
    ]
    connection = store.strava_connection()
    assert (connection.access_token, connection.refresh_token) == ("access-1", "refresh-1")


def test_a_connection_strava_no_longer_accepts_says_so(tmp_path):
    def rejecting(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, json={"message": "Authorization Error"})

    _, store = connected(tmp_path, rejecting)

    assert sync(store, rejecting) == REJECTED


def test_sync_now_runs_in_the_background_and_the_page_reports_it(tmp_path):
    fake = FakeStrava([summary(1, 1)])
    client, _ = connected(tmp_path, fake)

    response = client.post("/strava/sync", follow_redirects=False)
    client.app.state.strava_sync.join(timeout=10)

    assert response.headers["location"] == "/strava"
    page = client.get("/strava").text
    assert UP_TO_DATE in page
    assert len(client.get("/api/activities").json()) == 1


def test_a_sync_cut_short_by_a_restart_can_be_started_again(tmp_path):
    fake = FakeStrava([])
    _, store = connected(tmp_path, fake)
    assert store.start_strava_sync()
    assert not store.start_strava_sync()

    client = TestClient(create_app(data_dir=tmp_path, strava_transport=httpx2.MockTransport(fake)))

    assert "interrupted" in client.get("/strava").text
    assert store.start_strava_sync()


def test_without_an_api_application_the_page_explains_the_setup(tmp_path, monkeypatch):
    monkeypatch.delenv("MAKERUNDEV_STRAVA_CLIENT_ID")
    client = TestClient(create_app(data_dir=tmp_path))

    page = client.get("/strava")

    assert page.status_code == 200
    assert "MAKERUNDEV_STRAVA_CLIENT_ID" in page.text
    assert "<code>testserver</code>" in page.text
    assert "Connect with Strava" not in page.text
    assert client.post("/strava/connect", follow_redirects=False).headers["location"] == "/strava"

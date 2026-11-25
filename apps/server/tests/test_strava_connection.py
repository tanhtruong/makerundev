from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.db import connect
from makerundev_server.store import Store
from strava_fake import FakeStrava, connected, run, summary, sync, upload


def test_disconnect_removes_what_came_only_from_strava_even_if_revoking_fails(
    tmp_path, steady_run_fit
):
    fake = FakeStrava([summary(77, 1), summary(78, 2)])
    fake.revoke_fails = True
    client, store = connected(tmp_path, fake)
    upload(client, "morning.fit", steady_run_fit)
    sync(store, fake)
    assert (tmp_path / "streams" / "strava-78.parquet").exists()

    client.delete("/api/strava")

    activities = client.get("/api/activities").json()["items"]
    assert [(a["filename"], a["external_source"], a["external_id"]) for a in activities] == [
        ("morning.fit", None, None)
    ]
    assert not (tmp_path / "streams" / "strava-78.parquet").exists()
    assert not (tmp_path / "originals" / "strava-78").exists()
    assert store.strava_connection() is None
    assert client.get("/api/strava").json()["connected"] is False


def test_disconnect_revokes_the_token(tmp_path):
    fake = FakeStrava([])
    client, _ = connected(tmp_path, fake)

    client.delete("/api/strava")

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
    status = client.get("/api/strava")
    assert status.json()["connected"] is True
    assert "access-1" not in status.text and "refresh-1" not in status.text
    assert "application-secret" not in status.text


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


def test_without_an_api_application_strava_is_unconfigured_and_connect_goes_nowhere(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("MAKERUNDEV_STRAVA_CLIENT_ID")
    client = TestClient(create_app(data_dir=tmp_path))

    assert client.get("/api/strava").json()["configured"] is False
    assert client.post("/strava/connect", follow_redirects=False).headers["location"] == "/strava"


def test_a_sync_still_running_after_disconnect_stores_nothing(tmp_path):
    fake = FakeStrava([summary(5, 5), summary(4, 4)])
    client, store = connected(tmp_path, fake)
    removed = []
    fake.on_request["/activities/5"] = lambda: removed.append(client.delete("/api/strava"))
    assert store.strava_state.start()

    run(store, fake)

    assert [response.status_code for response in removed] == [200]
    assert (fake.stream_requests(), fake.detail_requests()) == (["5"], ["5"])
    assert client.get("/api/activities").json()["items"] == []
    assert store.strava_connection() is None
    assert not (tmp_path / "streams" / "strava-5.parquet").exists()

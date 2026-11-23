from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from fastapi.testclient import TestClient
from makerundev.io.strava import read_strava
from makerundev_server import create_app
from makerundev_server.db import connect
from makerundev_server.store import Store
from makerundev_server.strava import Unauthorized
from strava_fake import FakeStrava, connected, streams, summary, sync, upload


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
    activities = client.get("/api/activities").json()["items"]
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


def test_without_an_api_application_the_pages_open_and_connect_goes_nowhere(tmp_path, monkeypatch):
    monkeypatch.delenv("MAKERUNDEV_STRAVA_CLIENT_ID")
    client = TestClient(create_app(data_dir=tmp_path))

    assert client.get("/strava").status_code == 200
    assert client.post("/strava/connect", follow_redirects=False).headers["location"] == "/strava"


def test_a_sync_still_running_after_disconnect_stores_nothing(tmp_path):
    fake = FakeStrava([])
    client, store = connected(tmp_path, fake)
    held = summary(5, 5)
    activity = read_strava(held, streams())
    client.post("/strava/disconnect")

    with pytest.raises(Unauthorized):
        store.add_strava(held, streams(), activity, "backfill")
    with pytest.raises(Unauthorized):
        store.claim_strava(held, activity.start_time, "backfill")
    with pytest.raises(Unauthorized):
        store.skip_strava(held, activity.start_time, "no streams on Strava", "backfill")

    assert client.get("/api/activities").json()["items"] == []
    assert store.strava_connection() is None
    assert not (tmp_path / "streams" / "strava-5.parquet").exists()

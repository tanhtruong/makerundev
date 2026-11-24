import httpx2
import pytest
from fastapi.testclient import TestClient
from garmin_fake import KEY, FakeGarmin, app_with, sync
from makerundev_server import create_app
from makerundev_server.garmin import GarminClient
from makerundev_server.garmin_sync import GarminSync


def put_key(client, key=KEY):
    return client.put("/api/garmin/key", json={"key": key})


def test_status_reports_the_last_sync_and_what_it_skipped_without_the_key(
    tmp_path, make_fit, make_zip
):
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(1, 1)
    fake.run(2, 2, manualActivity=True)
    client, store = app_with(tmp_path, fake)
    put_key(client)
    sync(store, fake)

    response = client.get("/api/garmin")

    assert response.headers.get("cache-control") == "no-store"
    assert KEY not in response.text
    status = response.json()
    assert status["key_saved"] is True
    progress = status["sync"]
    assert progress["last_sync_at"].endswith("Z")
    assert {key: progress[key] for key in ("syncing", "imported", "matched", "outcome")} == {
        "syncing": False,
        "imported": 1,
        "matched": 0,
        "outcome": "up_to_date",
    }
    assert progress["skipped"] == [
        {
            "id": "2",
            "name": "Run 2",
            "start_time": "2026-03-02T07:00:00Z",
            "reason": "a manual entry, with no file",
            "url": "https://connect.garmin.com/modern/activity/2",
        }
    ]


def test_saving_a_key_garmin_accepts_stores_it(tmp_path, make_fit, make_zip):
    fake = FakeGarmin(make_fit, make_zip)
    client, store = app_with(tmp_path, fake)

    response = put_key(client, f"  {KEY}\n")

    assert response.status_code == 200
    assert response.json() == {
        "key_saved": True,
        "sync": {
            "syncing": False,
            "last_sync_at": None,
            "imported": 0,
            "matched": 0,
            "backfill_done": False,
            "backfill_before": None,
            "outcome": None,
            "resume_at": None,
            "skipped": [],
        },
    }
    assert KEY not in response.text
    connection = store.garmin.connection()
    assert connection is not None
    assert (connection.api_key, connection.token in fake.tokens) == (KEY, True)


@pytest.mark.parametrize(
    ("key", "message"),
    [
        (
            "a-key-from-another-account",
            "Garmin did not accept that key. Check it was copied whole and has not expired.",
        ),
        ("   ", "Paste your Personal API key first."),
    ],
)
def test_a_key_garmin_rejects_is_refused_at_the_field_and_not_saved(
    tmp_path, make_fit, make_zip, key, message
):
    fake = FakeGarmin(make_fit, make_zip)
    client, store = app_with(tmp_path, fake)

    response = put_key(client, key)

    assert response.status_code == 422
    assert [(e["loc"], e["msg"]) for e in response.json()["detail"]] == [(["body", "key"], message)]
    assert store.garmin.connection() is None


def connection_refused(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("connection refused", request=request)


@pytest.mark.parametrize(
    "garmin",
    [
        connection_refused,
        lambda request: httpx2.Response(429, headers={"Retry-After": "60"}),
        lambda request: httpx2.Response(503),
    ],
    ids=["connection refused", "rate limited", "server error"],
)
def test_a_key_that_cannot_be_checked_is_a_bad_gateway_and_not_saved(tmp_path, garmin):
    client = TestClient(
        create_app(data_dir=tmp_path, garmin_transport=httpx2.MockTransport(garmin), garmin_pause=0)
    )
    response = put_key(client)

    assert (response.status_code, response.json()) == (
        502,
        {"detail": "garmin could not be reached"},
    )
    assert client.get("/api/garmin").json() == {"key_saved": False, "sync": None}


def test_a_sync_cannot_start_before_a_key_is_saved(tmp_path, make_fit, make_zip):
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(1, 1)
    client, _ = app_with(tmp_path, fake)

    response = client.post("/api/garmin/sync")

    assert (response.status_code, response.json()) == (409, {"detail": "garmin key is not saved"})
    assert fake.downloads == []


def test_starting_a_sync_runs_it_in_the_background(tmp_path, make_fit, make_zip):
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(1, 1)
    fake.run(2, 2)
    client, _ = app_with(tmp_path, fake)
    put_key(client)

    response = client.post("/api/garmin/sync")
    client.app.state.garmin_sync.join(timeout=10)

    assert response.status_code == 202
    assert response.json()["key_saved"] is True
    progress = client.get("/api/garmin").json()["sync"]
    assert (progress["syncing"], progress["imported"], progress["outcome"]) == (
        False,
        2,
        "up_to_date",
    )


def test_removing_the_key_mid_sync_stops_it_and_keeps_imported_activities(
    tmp_path, make_fit, make_zip
):
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(1, 1)
    client, store = app_with(tmp_path, fake)
    put_key(client)
    sync(store, fake)
    fake.run(2, 2)
    removed = []
    fake.after_download = {"2": lambda: removed.append(client.delete("/api/garmin/key"))}

    assert store.garmin.start_sync()
    GarminSync(store, GarminClient(httpx2.MockTransport(fake), pause=0.0)).run()

    assert fake.downloads == ["1", "2"]
    assert [response.json() for response in removed] == [{"key_saved": False, "sync": None}]
    assert store.garmin.connection() is None
    activities = client.get("/api/activities").json()["items"]
    assert [a["filename"] for a in activities] == ["1_ACTIVITY.fit"]

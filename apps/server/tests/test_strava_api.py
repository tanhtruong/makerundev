import httpx2
from fastapi.testclient import TestClient
from makerundev_server import create_app
from strava_fake import FakeStrava, connected, summary, sync, upload


def test_status_reports_the_last_sync_and_what_it_skipped(tmp_path):
    fake = FakeStrava([summary(1, 1), summary(2, 2, manual=True)])
    client, store = connected(tmp_path, fake)
    sync(store, fake)

    response = client.get("/api/strava")

    assert response.headers.get("cache-control") == "no-store"
    status = response.json()
    assert (status["configured"], status["connected"]) == (True, True)
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
            "reason": "a manual entry, with no streams",
            "url": "https://www.strava.com/activities/2",
        }
    ]


def test_starting_a_sync_runs_it_in_the_background(tmp_path):
    fake = FakeStrava([summary(1, 1), summary(2, 2)])
    client, _ = connected(tmp_path, fake)

    response = client.post("/api/strava/sync")
    client.app.state.strava_sync.join(timeout=10)

    assert response.status_code == 202
    assert response.json()["connected"] is True
    progress = client.get("/api/strava").json()["sync"]
    assert (progress["syncing"], progress["imported"], progress["outcome"]) == (
        False,
        2,
        "up_to_date",
    )


def test_a_sync_cannot_start_before_strava_is_connected(tmp_path):
    fake = FakeStrava([summary(1, 1)])
    client = TestClient(create_app(data_dir=tmp_path, strava_transport=httpx2.MockTransport(fake)))

    response = client.post("/api/strava/sync")

    assert (response.status_code, response.json()) == (409, {"detail": "strava is not connected"})
    assert fake.requests == []


def test_disconnecting_reports_how_many_activities_it_removed(tmp_path, steady_run_fit):
    fake = FakeStrava([summary(77, 1), summary(78, 2)])
    client, store = connected(tmp_path, fake)
    upload(client, "morning.fit", steady_run_fit)
    sync(store, fake)

    response = client.delete("/api/strava")

    assert response.json() == {"removed_activities": 1}
    activities = client.get("/api/activities").json()["items"]
    assert [a["filename"] for a in activities] == ["morning.fit"]
    assert client.get("/api/strava").json()["connected"] is False

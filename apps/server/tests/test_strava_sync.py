import datetime as dt
import gzip
import json

import httpx2
from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.settings import AthleteSettings
from makerundev_server.sync import PAUSED_DAILY, PAUSED_SHORT, REJECTED, UP_TO_DATE
from strava_fake import FakeStrava, connected, summary, sync


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


def test_an_activity_strava_refuses_to_serve_is_skipped_and_the_sync_goes_on(tmp_path):
    fake = FakeStrava([summary(1, 1), summary(2, 2), summary(3, 3)])
    fake.refused.add("2")
    client, store = connected(tmp_path, fake)

    assert sync(store, fake) == UP_TO_DATE

    assert [a["external_id"] for a in client.get("/api/activities").json()] == ["3", "1"]
    assert [item["reason"] for item in store.strava_connection().skipped] == ["Strava answered 403"]


def test_an_activity_without_a_start_time_does_not_stop_the_sync(tmp_path):
    fake = FakeStrava([summary(1, 1), summary(2, 2)])
    broken = {"id": 9, "name": "Broken", "start_date": "2026-03-05T07:00:00Z"}
    fake.activities.append(broken)
    client, store = connected(tmp_path, fake)
    listed = fake.listed

    def without_start(params):
        return [
            {k: v for k, v in a.items() if a["id"] != 9 or k != "start_date"}
            for a in listed(params)
        ]

    fake.listed = without_start

    assert sync(store, fake) == UP_TO_DATE

    assert [a["external_id"] for a in client.get("/api/activities").json()] == ["2", "1"]

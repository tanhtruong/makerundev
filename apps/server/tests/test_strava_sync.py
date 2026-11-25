import datetime as dt
import gzip
import json
import sqlite3

import httpx2
from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.settings import AthleteSettings
from settings_payload import SETTINGS
from strava_fake import FakeStrava, connected, lap, summary, sync, upload


def test_first_sync_brings_in_every_activity_with_its_stream(tmp_path):
    fake = FakeStrava([summary(1, 1), summary(2, 2), summary(3, 3)])
    fake.laps["3"] = [
        lap("2026-03-03T07:00:00Z", 300, 1000.0),
        lap("2026-03-03T07:05:00Z", 700, 2000.0),
    ]
    client, store = connected(tmp_path, fake)
    store.save_athlete_settings(AthleteSettings(max_hr=190, resting_hr=50))

    assert sync(store, fake) == "up_to_date"

    assert fake.stream_requests() == ["3", "2", "1"]
    activities = client.get("/api/activities").json()["items"]
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
    assert newest["start_time"] == "2026-03-03T07:00:00Z"
    assert newest["trimp"] > 0
    records = client.get(f"/api/activities/{newest['id']}/records").json()
    assert records[0]["cadence"] == 170.0
    detail = client.get(f"/api/activities/{newest['id']}").json()
    assert detail["strava_url"] == "https://www.strava.com/activities/3"
    assert detail["laps"] == TWO_LAPS
    original = json.loads(gzip.decompress((tmp_path / "originals" / "strava-3").read_bytes()))
    assert original["activity"]["id"] == 3
    assert [item["distance"] for item in original["activity"]["laps"]] == [1000.0, 2000.0]
    connection = store.strava_connection()
    assert (connection.imported, connection.matched, connection.backfill_done) == (3, 0, True)


FACTS = (
    "distance_m, elapsed_s, moving_s, pace_s_per_km, avg_heart_rate, max_heart_rate,"
    " elevation_gain_m, trimp, laps, best_efforts, facts_version"
)


def stored_facts(data_dir) -> list[tuple]:
    with sqlite3.connect(data_dir / "makerundev.db") as db:
        return db.execute(f"SELECT {FACTS} FROM activities").fetchall()


def test_a_strava_activity_and_the_same_run_as_a_file_store_the_same_facts(tmp_path, make_fit):
    fake = FakeStrava([summary(1, 1)])
    _client, store = connected(tmp_path / "strava", fake)
    store.save_athlete_settings(AthleteSettings(max_hr=190, resting_hr=50))
    sync(store, fake)
    rows = [
        {"t": float(i), "lat": 55.67 + i * 0.00003, "lon": 12.56, "distance": i * 3.0, "hr": 140}
        for i in range(1001)
    ]
    client = TestClient(create_app(data_dir=tmp_path / "file"))
    client.put("/api/settings", json=SETTINGS)
    upload(client, "run.fit", make_fit(rows))

    [synced] = stored_facts(tmp_path / "strava")
    assert stored_facts(tmp_path / "file") == [synced]
    assert synced[7] > 0
    assert len(json.loads(synced[9])) >= 2


def test_a_sync_stopped_between_import_and_progress_neither_duplicates_nor_skips(
    tmp_path, monkeypatch
):
    fake = FakeStrava([summary(1, 1), summary(2, 2), summary(3, 3)])
    client, store = connected(tmp_path, fake)
    record = store.strava_state.record_import
    calls = []

    def stop_once(*args):
        calls.append(args)
        if len(calls) == 1:
            raise RuntimeError("stopped")
        record(*args)

    monkeypatch.setattr(store.strava_state, "record_import", stop_once)

    assert sync(store, fake) == "failed"
    assert sync(store, fake) == "up_to_date"

    assert fake.stream_requests() == ["3", "2", "1"]
    activities = client.get("/api/activities").json()["items"]
    assert [a["external_id"] for a in activities] == ["3", "2", "1"]
    assert store.strava_connection().backfill_done is True


TWO_LAPS = [
    {"number": 1, "distance_m": 1000.0, "elapsed_s": 300.0, "pace_s_per_km": 300.0},
    {"number": 2, "distance_m": 2000.0, "elapsed_s": 700.0, "pace_s_per_km": 350.0},
]


def laps(client: TestClient, activity_id: int) -> list[dict[str, float]]:
    found: list[dict[str, float]] = client.get(f"/api/activities/{activity_id}").json()["laps"]
    return found


def test_a_later_sync_only_asks_for_what_is_new(tmp_path):
    fake = FakeStrava([summary(1, 1), summary(2, 2)])
    client, store = connected(tmp_path, fake)
    sync(store, fake)
    fake.activities.append(summary(3, 3))
    fake.requests.clear()

    assert sync(store, fake) == "up_to_date"

    assert fake.stream_requests() == ["3"]
    assert len(client.get("/api/activities").json()["items"]) == 3
    assert store.strava_connection().imported == 1


def test_sync_pauses_before_the_rate_limit_and_resumes_where_it_stopped(tmp_path):
    fake = FakeStrava([summary(i, i) for i in range(1, 9)], limit=(10, 1000))
    client, store = connected(tmp_path, fake)

    assert sync(store, fake) == "paused_short"

    assert fake.usage[0] == 5
    assert fake.stream_requests() == ["8", "7"]
    assert store.strava_connection().backfill_done is False
    fake.limit = (100, 1000)

    assert sync(store, fake) == "up_to_date"

    assert fake.stream_requests() == ["8", "7", "6", "5", "4", "3", "2", "1"]
    assert len(client.get("/api/activities").json()["items"]) == 8


def test_sync_pauses_for_the_day_when_the_daily_limit_is_close(tmp_path):
    fake = FakeStrava([summary(1, 1), summary(2, 2)], limit=(100, 21))
    _, store = connected(tmp_path, fake)

    assert sync(store, fake) == "paused_daily"

    assert fake.stream_requests() == []


def test_activities_without_usable_streams_are_listed_and_not_tried_again(tmp_path):
    fake = FakeStrava(
        [summary(1, 1), summary(2, 2, manual=True), summary(3, 3), summary(4, 4)],
        without_streams=[3],
    )
    fake.broken_streams["4"] = {"time": {"data": []}}
    client, store = connected(tmp_path, fake)

    assert sync(store, fake) == "up_to_date"

    assert fake.stream_requests() == ["4", "3", "1"]
    assert [a["external_id"] for a in client.get("/api/activities").json()["items"]] == ["1"]
    skipped = {item["id"]: item["reason"] for item in store.strava_connection().skipped}
    assert skipped == {
        "2": "a manual entry, with no streams",
        "3": "no streams on Strava",
        "4": "the Strava activity has no time stream",
    }
    fake.requests.clear()

    sync(store, fake)

    assert fake.stream_requests() == []


def test_an_access_token_about_to_expire_is_refreshed_and_the_new_pair_kept(tmp_path):
    fake = FakeStrava([summary(1, 1)])
    soon = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=30)
    _, store = connected(tmp_path, fake, expires_at=soon)

    assert sync(store, fake) == "up_to_date"

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


def test_a_sync_cut_short_by_a_restart_can_be_started_again(tmp_path):
    fake = FakeStrava([])
    _, store = connected(tmp_path, fake)
    assert store.strava_state.start()
    assert not store.strava_state.start()

    client = TestClient(create_app(data_dir=tmp_path, strava_transport=httpx2.MockTransport(fake)))

    assert client.get("/api/strava").json()["sync"]["outcome"] == "interrupted"
    assert store.strava_state.start()


def test_an_activity_strava_refuses_to_serve_is_skipped_and_the_sync_goes_on(tmp_path):
    fake = FakeStrava([summary(1, 1), summary(2, 2), summary(3, 3)])
    fake.refused.add("2")
    client, store = connected(tmp_path, fake)

    assert sync(store, fake) == "up_to_date"

    assert [a["external_id"] for a in client.get("/api/activities").json()["items"]] == ["3", "1"]
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

    assert sync(store, fake) == "up_to_date"

    assert [a["external_id"] for a in client.get("/api/activities").json()["items"]] == ["2", "1"]


def test_an_activity_cut_off_between_its_streams_and_its_laps_comes_in_whole_next_time(tmp_path):
    fake = FakeStrava([summary(1, 1)])
    fake.laps["1"] = [
        lap("2026-03-01T07:00:00Z", 300, 1000.0),
        lap("2026-03-01T07:05:00Z", 700, 2000.0),
    ]
    fake.throttled_detail.add("1")
    client, store = connected(tmp_path, fake)

    assert sync(store, fake) == "paused_short"

    assert fake.stream_requests() == ["1"]
    assert client.get("/api/activities").json()["items"] == []
    fake.throttled_detail.clear()

    assert sync(store, fake) == "up_to_date"

    [activity] = client.get("/api/activities").json()["items"]
    assert laps(client, activity["id"]) == TWO_LAPS


def test_activities_synced_before_laps_get_them_once_on_a_later_sync(tmp_path, steady_run_fit):
    fake = FakeStrava([summary(1, 1), summary(2, 2), summary(77, 9, distance=9000.0)])
    client, store = connected(tmp_path, fake)
    upload(client, "77.fit.gz", gzip.compress(steady_run_fit))
    sync(store, fake)
    with sqlite3.connect(tmp_path / "makerundev.db") as db:
        db.execute("UPDATE activities SET laps = NULL, facts_version = 0")
    client = TestClient(create_app(data_dir=tmp_path, strava_transport=httpx2.MockTransport(fake)))
    fake.laps["1"] = [
        lap("2026-03-01T07:05:00Z", 700, 2000.0),
        lap("2026-03-01T07:00:00Z", 300, 1000.0),
    ]
    fake.without_detail.add("2")
    fake.requests.clear()
    ids = {a["external_id"]: a["id"] for a in client.get("/api/activities").json()["items"]}
    assert laps(client, ids["1"]) == []

    assert sync(store, fake) == "up_to_date"

    assert fake.stream_requests() == []
    assert sorted(fake.detail_requests()) == ["1", "2"]
    assert laps(client, ids["1"]) == TWO_LAPS
    original = json.loads(gzip.decompress((tmp_path / "originals" / "strava-1").read_bytes()))
    assert len(original["activity"]["laps"]) == 2
    assert len(original["streams"]["time"]["data"]) == 1001
    assert laps(client, ids["2"]) == []
    fake.requests.clear()

    assert sync(store, fake) == "up_to_date"

    assert fake.detail_requests() == []

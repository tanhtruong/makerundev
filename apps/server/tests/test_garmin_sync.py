import datetime as dt
import hashlib

from garmin_fake import FakeGarmin, app_with, listing, run_start, save_key, sync
from makerundev.io.strava import read_strava
from makerundev_server import garmin
from makerundev_server.garmin import Token
from makerundev_server.strava import Tokens
from strava_fake import FAR, streams, summary, upload


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_a_saved_key_syncs_every_activity_as_a_file_newest_first(tmp_path, make_fit, make_zip):
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(1, 1)
    fake.run(2, 2)
    fake.run(3, 3, entry_name="3.x.fit")
    client, store = app_with(tmp_path, fake)

    save_key(client)
    client.post("/api/garmin/sync")
    client.app.state.garmin_sync.join(timeout=10)

    assert fake.downloads == ["3", "2", "1"]
    activities = client.get("/api/activities").json()["items"]
    assert [
        (a["filename"], a["name"], a["external_source"], a["start_time"]) for a in activities
    ] == [
        ("garmin-3.fit", "Run 3", None, "2026-03-03T07:00:00Z"),
        ("2_ACTIVITY.fit", "Run 2", None, "2026-03-02T07:00:00Z"),
        ("1_ACTIVITY.fit", "Run 1", None, "2026-03-01T07:00:00Z"),
    ]
    assert {row.sha256 for row in store.list()} == {sha256(fake.fit(day)) for day in (1, 2, 3)}
    assert client.get("/api/garmin").json()["sync"]["outcome"] == "up_to_date"

    fake.run(4, 4)
    client.post("/api/garmin/sync")
    client.app.state.garmin_sync.join(timeout=10)

    assert fake.downloads == ["3", "2", "1", "4"]
    assert fake.tokens_issued == 1
    assert store.garmin.connection().imported == 1


def test_runs_already_here_are_not_downloaded_and_strava_only_ones_are_replaced(
    tmp_path, make_fit, make_zip
):
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(1, 1)
    fake.run(2, 2)
    fake.run(3, 3)
    client, store = app_with(tmp_path, fake)
    upload(client, "watch.fit", fake.fit(1, heart_rate=150))
    upload(client, "unnamed.fit", fake.fit(3, heart_rate=150))
    store.save_strava_tokens(Tokens("access", "refresh", FAR))
    assert store.claim_strava(summary(8, 1), run_start(1), "backfill")
    strava_run = summary(7, 2)
    store.add_strava(strava_run, streams(), read_strava(strava_run, streams()), "backfill")
    save_key(client)

    assert sync(store, fake) == "up_to_date"

    assert fake.downloads == ["2"]
    rows = {row.start_time.day: row for row in store.list()}
    assert sorted(rows) == [1, 2, 3]
    assert (rows[1].filename, rows[1].name) == ("watch.fit", "Run 8")
    assert (rows[2].filename, rows[2].name, rows[2].sha256, rows[2].external_id) == (
        "2_ACTIVITY.fit",
        "Run 7",
        sha256(fake.fit(2)),
        "7",
    )
    assert (rows[3].filename, rows[3].name) == ("unnamed.fit", "Run 3")
    connection = store.garmin.connection()
    assert (connection.imported, connection.matched) == (1, 2)


def test_the_garmin_name_wins_over_the_name_in_the_downloaded_file(tmp_path, make_fit, make_zip):
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(1, 1)
    gpx = (
        '<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">'
        "<trk><name>Track name</name><trkseg>"
        '<trkpt lat="55.67" lon="12.56"><time>2026-03-01T07:00:00Z</time></trkpt>'
        '<trkpt lat="55.68" lon="12.56"><time>2026-03-01T07:05:00Z</time></trkpt>'
        "</trkseg></trk></gpx>"
    )
    fake.files["1"] = make_zip(("1_ACTIVITY.gpx", gpx.encode()))
    client, store = app_with(tmp_path, fake)
    save_key(client)

    assert sync(store, fake) == "up_to_date"

    assert [(row.source_format, row.name) for row in store.list()] == [("gpx", "Run 1")]


def test_a_throttled_sync_stops_and_the_next_one_resumes_where_it_stopped(
    tmp_path, make_fit, make_zip
):
    fake = FakeGarmin(make_fit, make_zip)
    for day in range(1, 5):
        fake.run(day, day)
    client, store = app_with(tmp_path, fake)
    save_key(client)
    fake.throttle_after = 3

    before = dt.datetime.now(dt.UTC)
    assert sync(store, fake) == "paused"
    resume_at = dt.datetime.fromisoformat(client.get("/api/garmin").json()["sync"]["resume_at"])
    assert (
        before + dt.timedelta(seconds=120)
        <= resume_at
        <= dt.datetime.now(dt.UTC) + dt.timedelta(seconds=120)
    )

    assert fake.downloads == ["4", "3"]
    assert store.garmin.connection().backfill_done is False
    fake.throttle_after = None
    token = store.garmin.connection().token
    store.garmin.save_token(Token(token, dt.datetime.now(dt.UTC) + dt.timedelta(minutes=10)))

    assert sync(store, fake) == "up_to_date"

    assert fake.downloads == ["4", "3", "2", "1"]
    assert len(store.list()) == 4
    connection = store.garmin.connection()
    assert (connection.imported, connection.matched) == (2, 1)
    assert fake.tokens_issued == 2


def test_activities_deleted_on_garmin_during_a_sync_do_not_hide_older_ones(
    tmp_path, make_fit, make_zip, monkeypatch
):
    monkeypatch.setattr(garmin, "PAGE_SIZE", 3)
    fake = FakeGarmin(make_fit, make_zip)
    for day in range(1, 8):
        fake.run(day, day)
    fake.after_download = {"5": lambda: fake.delete("7")}
    client, store = app_with(tmp_path, fake)
    save_key(client)

    assert sync(store, fake) == "up_to_date"

    assert fake.downloads == ["7", "6", "5", "4", "3", "2", "1"]
    assert len(store.list()) == 7


def test_a_crowded_day_does_not_end_the_backfill_early(tmp_path, make_fit, make_zip, monkeypatch):
    monkeypatch.setattr(garmin, "PAGE_SIZE", 3)
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(1, 1)
    for activity_id, minute in ((2, 0), (3, 10), (4, 20), (5, 30)):
        fake.run(activity_id, 5, minute=minute)
    client, store = app_with(tmp_path, fake)
    save_key(client)

    assert sync(store, fake) == "up_to_date"

    assert fake.downloads == ["5", "4", "3", "2", "1"]
    assert len(store.list()) == 5


def test_runs_starting_in_the_same_second_are_both_imported(
    tmp_path, make_fit, make_zip, monkeypatch
):
    monkeypatch.setattr(garmin, "PAGE_SIZE", 3)
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(5, 4)
    fake.run(4, 3)
    fake.run(3, 2)
    fake.run(2, 2, step=5.0)
    fake.run(1, 1)
    client, store = app_with(tmp_path, fake)
    save_key(client)

    assert sync(store, fake) == "up_to_date"

    assert fake.downloads == ["5", "4", "3", "2", "1"]
    assert sorted(row.distance_m for row in store.list()) == [3000.0] * 4 + [5000.0]


def test_activities_that_cannot_be_imported_are_listed_and_not_downloaded_again(
    tmp_path, make_fit, make_zip
):
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(1, 1)
    fake.listed.append({k: v for k, v in listing(2, 2).items() if k != "startTimeGMT"})
    fake.listed.append(listing(3, 3, manualActivity=True))
    fake.run(4, 4)
    fake.files["4"] = make_zip(("swim.fit", fake.fit(4)), ("bike.fit", fake.fit(6)))
    fake.run(5, 5)
    fake.files["5"] = fake.fit(5)
    client, store = app_with(tmp_path, fake)
    save_key(client)

    assert sync(store, fake) == "up_to_date"
    assert sync(store, fake) == "up_to_date"

    assert fake.downloads == ["5", "4", "1"]
    assert [(item["id"], item["reason"]) for item in store.garmin.connection().skipped] == [
        ("3", "a manual entry, with no file"),
        ("4", "ZIP holds more than one activity file; extract it and import the files"),
        ("5", "Garmin did not send a ZIP"),
    ]
    assert [a["filename"] for a in client.get("/api/activities").json()["items"]] == [
        "1_ACTIVITY.fit"
    ]


def test_retry_after_is_read_as_seconds_or_as_a_date():
    now = dt.datetime(2026, 11, 21, 12, 0, tzinfo=dt.UTC)

    assert garmin.retry_at("120", now) == dt.datetime(2026, 11, 21, 12, 2, tzinfo=dt.UTC)
    assert garmin.retry_at("61", now) == dt.datetime(2026, 11, 21, 12, 1, 1, tzinfo=dt.UTC)
    assert garmin.retry_at("Sat, 21 Nov 2026 12:05:00 GMT", now) == dt.datetime(
        2026, 11, 21, 12, 5, tzinfo=dt.UTC
    )
    assert garmin.retry_at("9" * 30, now) is None
    assert garmin.retry_at("soon", now) is None
    assert garmin.retry_at(None, now) is None

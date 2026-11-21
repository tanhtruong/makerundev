import datetime as dt
import hashlib

from garmin_fake import KEY, FakeGarmin, app_with, listing, save_key, sync
from makerundev.io.strava import read_strava
from makerundev_server import garmin
from makerundev_server.garmin import Token
from makerundev_server.strava import Tokens
from makerundev_server.sync_state import UP_TO_DATE
from strava_fake import FAR, streams, summary, upload


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_a_saved_key_syncs_every_activity_as_a_file_newest_first(tmp_path, make_fit, make_zip):
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(1, 1)
    fake.run(2, 2)
    fake.run(3, 3, entry_name="3.x.fit")
    client, store = app_with(tmp_path, fake)

    assert save_key(client).headers["location"] == "/garmin?notice=saved"
    client.post("/garmin/sync")
    client.app.state.garmin_sync.join(timeout=10)

    assert fake.downloads == ["3", "2", "1"]
    activities = client.get("/api/activities").json()
    assert [(a["filename"], a["external_source"], a["start_time"]) for a in activities] == [
        ("garmin-3.fit", None, "2026-03-03T07:00:00+00:00"),
        ("2_ACTIVITY.fit", None, "2026-03-02T07:00:00+00:00"),
        ("1_ACTIVITY.fit", None, "2026-03-01T07:00:00+00:00"),
    ]
    assert {row.sha256 for row in store.list()} == {sha256(fake.fit(day)) for day in (1, 2, 3)}
    page = client.get("/garmin").text
    assert UP_TO_DATE in page
    assert KEY not in page

    fake.run(4, 4)
    client.post("/garmin/sync")
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
    client, store = app_with(tmp_path, fake)
    upload(client, "watch.fit", fake.fit(1, heart_rate=150))
    store.save_strava_tokens(Tokens("access", "refresh", FAR))
    strava_run = summary(7, 2)
    store.add_strava(strava_run, streams(), read_strava(strava_run, streams()), "backfill")
    save_key(client)

    assert sync(store, fake) == UP_TO_DATE

    assert fake.downloads == ["2"]
    rows = {row.start_time.day: row for row in store.list()}
    assert sorted(rows) == [1, 2]
    assert rows[1].filename == "watch.fit"
    assert (rows[2].filename, rows[2].sha256, rows[2].external_id) == (
        "2_ACTIVITY.fit",
        sha256(fake.fit(2)),
        "7",
    )
    connection = store.garmin.connection()
    assert (connection.imported, connection.matched) == (1, 1)


def test_a_throttled_sync_stops_and_the_next_one_resumes_where_it_stopped(
    tmp_path, make_fit, make_zip
):
    fake = FakeGarmin(make_fit, make_zip)
    for day in range(1, 5):
        fake.run(day, day)
    client, store = app_with(tmp_path, fake)
    save_key(client)
    fake.throttle_after = 3

    assert "Sync again in 2 minutes." in sync(store, fake)

    assert fake.downloads == ["4", "3"]
    assert store.garmin.connection().backfill_done is False
    fake.throttle_after = None
    token = store.garmin.connection().token
    store.garmin.save_token(Token(token, dt.datetime.now(dt.UTC) + dt.timedelta(minutes=10)))

    assert sync(store, fake) == UP_TO_DATE

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

    assert sync(store, fake) == UP_TO_DATE

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

    assert sync(store, fake) == UP_TO_DATE

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

    assert sync(store, fake) == UP_TO_DATE

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

    assert sync(store, fake) == UP_TO_DATE
    assert sync(store, fake) == UP_TO_DATE

    assert fake.downloads == ["5", "4", "1"]
    assert [(item["id"], item["reason"]) for item in store.garmin.connection().skipped] == [
        ("3", "a manual entry, with no file"),
        ("4", "ZIP holds more than one activity file; extract it and import the files"),
        ("5", "Garmin did not send a ZIP"),
    ]
    assert [a["filename"] for a in client.get("/api/activities").json()] == ["1_ACTIVITY.fit"]


def test_retry_after_is_read_as_seconds_or_as_a_date():
    now = dt.datetime(2026, 11, 21, 12, 0, tzinfo=dt.UTC)

    assert garmin.retry_minutes("120", now) == 2
    assert garmin.retry_minutes("61", now) == 2
    assert garmin.retry_minutes("Sat, 21 Nov 2026 12:05:00 GMT", now) == 5
    assert garmin.retry_minutes("Sat, 21 Nov 2026 11:00:00 GMT", now) == 1
    assert garmin.retry_minutes("soon", now) is None
    assert garmin.retry_minutes(None, now) is None

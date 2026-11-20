import datetime as dt
import gzip

import pytest
from makerundev_server.store import same_activity
from makerundev_server.sync import UP_TO_DATE
from strava_fake import FIT_START, FakeStrava, connected, summary, sync, upload


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

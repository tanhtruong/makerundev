import httpx2
from garmin_fake import FakeGarmin, app_with, save_key, sync
from makerundev_server.garmin import GarminClient
from makerundev_server.garmin_sync import GarminSync


def test_a_key_garmin_rejects_is_not_saved(tmp_path, make_fit, make_zip):
    fake = FakeGarmin(make_fit, make_zip)
    client, store = app_with(tmp_path, fake)

    response = save_key(client, "a-key-from-another-account")

    assert response.headers["location"] == "/garmin?notice=rejected"
    assert store.garmin.connection() is None


def test_removing_the_key_keeps_imported_activities_and_stops_a_running_sync(
    tmp_path, make_fit, make_zip
):
    fake = FakeGarmin(make_fit, make_zip)
    fake.run(1, 1)
    client, store = app_with(tmp_path, fake)
    save_key(client)
    sync(store, fake)
    fake.run(2, 2)
    fake.after_download = {"2": lambda: client.post("/garmin/remove")}

    assert store.garmin.start_sync()
    GarminSync(store, GarminClient(httpx2.MockTransport(fake), pause=0.0)).run()

    assert fake.downloads == ["1", "2"]
    assert store.garmin.connection() is None
    assert [a["filename"] for a in client.get("/api/activities").json()["items"]] == [
        "1_ACTIVITY.fit"
    ]

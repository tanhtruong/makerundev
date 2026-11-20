from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.db import connect
from makerundev_server.settings import AthleteSettings
from makerundev_server.store import Store


def test_uploaded_activity_is_listed_once_and_viewable(tmp_path, steady_run_fit):
    client = TestClient(create_app(data_dir=tmp_path))

    for _ in range(2):
        response = client.post(
            "/activities",
            files=[("files", ("morning.fit", steady_run_fit, "application/octet-stream"))],
        )
        assert response.status_code == 200

    activities = client.get("/api/activities").json()
    assert len(activities) == 1
    assert activities[0]["distance_m"] == 3000.0
    assert activities[0]["sport"] == "running"
    assert activities[0]["start_time"] == "2026-03-01T07:00:00+00:00"

    index = client.get("/")
    assert "morning.fit" in index.text
    assert "3.00 km" in index.text

    detail = client.get(f"/activities/{activities[0]['id']}")
    assert detail.status_code == 200
    assert "5:33 /km" in detail.text


def test_imported_activity_gets_trimp_only_once_heart_rate_is_set(
    tmp_path, steady_run_fit, make_fit
):
    client = TestClient(create_app(data_dir=tmp_path))
    upload = [("files", ("before.fit", steady_run_fit, "application/octet-stream"))]
    client.post("/activities", files=upload)
    store = Store(tmp_path, connect(tmp_path))
    assert [row.trimp for row in store.list()] == [None]

    store.save_athlete_settings(AthleteSettings(max_hr=190, resting_hr=50))
    later = make_fit([{"t": float(i), "distance": i * 3.0, "hr": 150} for i in range(601)])
    client.post("/activities", files=[("files", ("after.fit", later, "application/octet-stream"))])

    trimp = {row.filename: row.trimp for row in store.list()}
    assert trimp["after.fit"] is not None and trimp["after.fit"] > 0

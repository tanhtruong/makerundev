from fastapi.testclient import TestClient
from pacelab_server import create_app


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

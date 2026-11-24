import pytest
from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.db import connect
from makerundev_server.store import Store
from settings_payload import SETTINGS


@pytest.mark.parametrize(
    "headers",
    [
        {"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"},
        {"Sec-Fetch-Site": "same-site", "Origin": "http://testserver:5173"},
        {"Origin": "https://evil.example"},
        {"Origin": "http://testserver:5173"},
        {"Origin": "http://testserver.evil.example"},
        {"Origin": "null", "Host": ""},
    ],
)
def test_a_cross_site_write_is_refused_and_changes_nothing(tmp_path, headers):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.put("/api/settings", json=SETTINGS, headers=headers)

    assert response.status_code == 403
    read = client.get("/api/settings", headers=headers)
    assert read.status_code == 200
    assert read.json()["settings"] is None


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Sec-Fetch-Site": "same-origin", "Origin": "https://run.example.com"},
        {"Sec-Fetch-Site": "none"},
        {"Origin": "https://testserver"},
    ],
)
def test_a_same_origin_or_header_less_write_goes_through(tmp_path, headers):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.put("/api/settings", json=SETTINGS, headers=headers)

    assert response.status_code == 200
    assert client.get("/api/settings").json()["settings"] == SETTINGS


def test_another_site_cannot_start_a_strava_connection(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    cross_site = {"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"}

    posted = client.post("/strava/connect", headers=cross_site, follow_redirects=False)
    linked = client.get("/strava/connect", headers=cross_site, follow_redirects=False)

    assert posted.status_code == 403
    assert "strava.com" not in linked.headers.get("location", "")
    assert Store(tmp_path, connect(tmp_path)).strava_connection() is None

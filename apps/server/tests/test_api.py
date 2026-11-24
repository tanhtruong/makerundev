import datetime as dt
from pathlib import Path

import openapi
import pytest
from fastapi.testclient import TestClient
from makerundev_server import create_app
from settings_payload import SETTINGS as BASE_SETTINGS

ROWS = [{"t": float(i), "distance": i * 3.0, "hr": 140} for i in range(301)]


def at(day: int) -> dt.datetime:
    return dt.datetime(2026, 3, day, 7, 0, tzinfo=dt.UTC)


@pytest.fixture
def client(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    uploads = [
        ("mon.fit", at(2), ROWS),
        ("tie-a.fit", at(4), ROWS),
        ("tie-b.fit", at(4), ROWS[:200]),
        ("tue.fit", at(3), ROWS),
        ("sun.fit", at(1), ROWS),
    ]
    for filename, start, rows in uploads:
        fit = make_fit(rows, start=start)
        response = client.post("/api/activities", files=[("files", (filename, fit))])
        assert response.status_code == 200
    return client


def test_activities_are_paged_newest_first_with_the_total(client):
    pages = [
        client.get("/api/activities", params={"limit": 2, "offset": offset}).json()
        for offset in (0, 2, 4)
    ]

    assert [[a["filename"] for a in page["items"]] for page in pages] == [
        ["tie-b.fit", "tie-a.fit"],
        ["tue.fit", "mon.fit"],
        ["sun.fit"],
    ]
    assert [page["total"] for page in pages] == [5, 5, 5]
    first = client.get("/api/activities").json()["items"][0]
    assert (first["start_time"], first["avg_heart_rate_bpm"]) == ("2026-03-04T07:00:00Z", 140.0)


@pytest.mark.parametrize("params", [{"limit": 201}, {"limit": 0}, {"offset": -1}])
def test_a_page_outside_the_limits_is_refused(client, params):
    response = client.get("/api/activities", params=params)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", next(iter(params))]


DETAIL_ROWS = [
    {
        "t": float(i),
        "lat": 55.67 + i * 0.00004,
        "lon": 12.56,
        "distance": i * 4.0,
        "speed": 4.0,
        "altitude": 10.0,
        "hr": 150,
        "power": 300,
        "stance_time": 250.0,
        "vertical_oscillation": 85.0,
        "step_length": 1100.0,
    }
    for i in range(1501)
]
SETTINGS = BASE_SETTINGS | {"body_mass_kg": 75}


def test_activity_detail_returns_what_the_activity_page_shows(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    client.put("/api/settings", json=SETTINGS)
    client.post("/api/activities", files=[("files", ("steady.fit", make_fit(DETAIL_ROWS)))])
    activity_id = client.get("/api/activities").json()["items"][0]["id"]

    detail = client.get(f"/api/activities/{activity_id}").json()

    assert detail["filename"] == "steady.fit"
    assert detail["distance_m"] == pytest.approx(6000.0)
    assert (detail["is_running"], detail["settings_set"], detail["body_mass_kg"]) == (
        True,
        True,
        75.0,
    )
    assert (detail["counts_for_performance"], detail["excluded_from_performance"]) == (True, False)
    assert detail["strava_url"] is None
    assert detail["grade_adjusted_pace_s_per_km"] == pytest.approx(250.0)
    assert detail["aerobic_decoupling_percent"] == pytest.approx(0.0, abs=1e-9)
    assert (detail["avg_power_w"], detail["avg_power_w_per_kg"]) == (300.0, 4.0)
    assert detail["estimated_power_w_per_kg"] == pytest.approx(detail["estimated_power_w"] / 75)
    assert detail["running_dynamics"] == {
        "ground_contact_time_ms": 250.0,
        "vertical_oscillation_mm": 85.0,
        "step_length_m": pytest.approx(1.1),
    }
    assert [(s["distance_m"], s["elapsed_s"]) for s in detail["splits"]] == [
        (pytest.approx(1000.0), pytest.approx(250.0))
    ] * 6
    assert detail["laps"] == []
    efforts = {e["distance_m"]: e["elapsed_s"] for e in detail["best_efforts"]}
    assert (efforts[1000.0], efforts[5000.0]) == (pytest.approx(250.0), pytest.approx(1250.0))
    assert [(z["name"], z["low_bpm"], z["high_bpm"], z["elapsed_s"]) for z in detail["zones"]] == [
        ("Zone 1", None, 113, 0.0),
        ("Zone 2", 114, 132, 0.0),
        ("Zone 3", 133, 151, 1500.0),
        ("Zone 4", 152, 170, 0.0),
        ("Zone 5", 171, None, 0.0),
    ]
    series = detail["series"]
    assert len(series) == 1000
    assert series[0] == {
        "distance_m": 0.0,
        "elapsed_s": 0.0,
        "pace_s_per_km": 250.0,
        "heart_rate_bpm": 150.0,
        "altitude_m": 10.0,
    }
    assert (series[-1]["distance_m"], series[-1]["elapsed_s"]) == (6000.0, 1500.0)
    assert detail["series_bounds"] == {
        "pace_s_per_km": {"low": 250.0, "high": 250.0},
        "heart_rate_bpm": {"low": 150.0, "high": 150.0},
        "altitude_m": {"low": 10.0, "high": 10.0},
    }
    shape = detail["route_shape"]
    assert (shape["width"], shape["height"]) == (0.0, pytest.approx(1000.0))
    assert shape["points"][0] == {"x": 0.0, "y": pytest.approx(1000.0)}
    assert shape["points"][-1] == {"x": 0.0, "y": 0.0}
    route = detail["route"]
    assert len(route) == 501
    assert route[0] == {"latitude_deg": pytest.approx(55.67), "longitude_deg": pytest.approx(12.56)}
    assert route[-1] == {
        "latitude_deg": pytest.approx(55.73),
        "longitude_deg": pytest.approx(12.56),
    }


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/activities/999", None),
        ("PUT", "/api/activities/999/exclusion", {"excluded": True}),
    ],
)
def test_an_unknown_activity_is_not_found(client, method, path, body):
    response = client.request(method, path, json=body)

    assert (response.status_code, response.json()) == (404, {"detail": "activity not found"})


def test_the_committed_openapi_schema_matches_the_app():
    committed = Path(openapi.SCHEMA).read_text()

    assert committed == openapi.render(), "apps/server/openapi.json is stale: run make openapi"

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from fastapi.testclient import TestClient
from fit_tool.profile.profile_type import Sport
from makerundev_server import create_app
from makerundev_server.db import connect
from makerundev_server.settings import AthleteSettings
from makerundev_server.store import Store


def test_uploaded_activity_is_listed(tmp_path, steady_run_fit):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.post(
        "/api/activities",
        files=[("files", ("morning.fit", steady_run_fit, "application/octet-stream"))],
    )
    assert response.status_code == 200

    activities = client.get("/api/activities").json()["items"]
    assert len(activities) == 1
    assert activities[0]["distance_m"] == 3000.0
    assert activities[0]["sport"] == "running"
    assert activities[0]["start_time"] == "2026-03-01T07:00:00Z"


def test_api_import_reports_each_file_in_order_and_lists_the_new_activity_once(
    tmp_path, steady_run_fit
):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.post(
        "/api/activities",
        files=[
            ("files", ("morning.fit", steady_run_fit, "application/octet-stream")),
            ("files", ("again.fit", steady_run_fit, "application/octet-stream")),
            ("files", ("notes.txt", b"not an activity", "text/plain")),
        ],
    )

    assert response.status_code == 200
    [activity] = client.get("/api/activities").json()["items"]
    assert response.json() == {
        "results": [
            {
                "filename": "morning.fit",
                "status": "imported",
                "activity_id": activity["id"],
                "error": None,
            },
            {
                "filename": "again.fit",
                "status": "already_imported",
                "activity_id": activity["id"],
                "error": None,
            },
            {
                "filename": "notes.txt",
                "status": "failed",
                "activity_id": None,
                "error": "unsupported file: expected FIT, GPX or TCX",
            },
        ]
    }
    assert activity["filename"] == "morning.fit"


LAP_ROWS = [{"t": float(i), "distance": i * 3.0} for i in range(601)]
LAPS = [
    {"t": 0.0, "elapsed": 330.0, "distance": 1000.0},
    {"t": 330.0, "elapsed": 270.0, "distance": 800.0},
]
DETAIL_LAPS = [
    {"number": 1, "distance_m": 1000.0, "elapsed_s": 330.0, "pace_s_per_km": 330.0},
    {"number": 2, "distance_m": 800.0, "elapsed_s": 270.0, "pace_s_per_km": 337.5},
]


def detail(client: TestClient, activity_id: int) -> dict[str, Any]:
    response = client.get(f"/api/activities/{activity_id}")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_uploaded_activity_keeps_its_laps_with_their_pace(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    fit = make_fit(LAP_ROWS, laps=LAPS)
    client.post("/api/activities", files=[("files", ("laps.fit", fit, "application/octet-stream"))])
    activity_id = client.get("/api/activities").json()["items"][0]["id"]

    with sqlite3.connect(tmp_path / "makerundev.db") as db:
        stored = json.loads(db.execute("SELECT laps FROM activities").fetchone()[0])
    assert stored == [
        {"start_time": "2026-03-01T07:00:00+00:00", "elapsed_s": 330.0, "distance_m": 1000.0},
        {"start_time": "2026-03-01T07:05:30+00:00", "elapsed_s": 270.0, "distance_m": 800.0},
    ]
    assert detail(client, activity_id)["laps"] == DETAIL_LAPS


def test_activity_imported_before_laps_were_stored_gets_them_on_first_view(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    fit = make_fit(LAP_ROWS, laps=LAPS)
    client.post("/api/activities", files=[("files", ("laps.fit", fit, "application/octet-stream"))])
    activity_id = client.get("/api/activities").json()["items"][0]["id"]
    with sqlite3.connect(tmp_path / "makerundev.db") as db:
        db.execute("UPDATE activities SET laps = NULL")

    assert detail(client, activity_id)["laps"] == DETAIL_LAPS
    (tmp_path / "originals" / hashlib.sha256(fit).hexdigest()).unlink()
    assert detail(client, activity_id)["laps"] == DETAIL_LAPS


def test_outdoor_activity_has_a_route_and_treadmill_run_has_none(
    tmp_path, steady_run_fit, make_fit
):
    client = TestClient(create_app(data_dir=tmp_path))
    treadmill = make_fit(LAP_ROWS)
    for name, fit in (("outdoor.fit", steady_run_fit), ("treadmill.fit", treadmill)):
        client.post("/api/activities", files=[("files", (name, fit, "application/octet-stream"))])
    ids = {row["filename"]: row["id"] for row in client.get("/api/activities").json()["items"]}

    outdoor = detail(client, ids["outdoor.fit"])["route"]
    assert len(outdoor) > 2
    assert detail(client, ids["treadmill.fit"])["route"] is None


DYNAMICS_COLUMNS = ["ground_contact_time", "vertical_oscillation", "step_length"]
DYNAMICS_ROWS = [
    {
        "t": float(i),
        "distance": i * 3.0,
        "stance_time": 250.0,
        "vertical_oscillation": 85.0,
        "step_length": 1100.0,
    }
    for i in range(601)
]
DYNAMICS = {
    "ground_contact_time_ms": 250.0,
    "vertical_oscillation_mm": 85.0,
    "step_length_m": pytest.approx(1.1),
}
NO_DYNAMICS = dict.fromkeys(DYNAMICS)


def upload(client: TestClient, filename: str, data: bytes) -> int:
    client.post("/api/activities", files=[("files", (filename, data, "application/octet-stream"))])
    activity_id: int = next(
        row["id"]
        for row in client.get("/api/activities").json()["items"]
        if row["filename"] == filename
    )
    return activity_id


def test_activity_detail_gives_grade_adjusted_pace_and_decoupling_and_marks_a_ride(
    tmp_path, make_fit
):
    client = TestClient(create_app(data_dir=tmp_path))
    hill = [
        {
            "t": i * 3.0,
            "distance": i * 10.0,
            "altitude": 200 + i * 1.0,
            "hr": 140 if i < 150 else 147,
        }
        for i in range(301)
    ]
    bare = [{"t": float(i), "distance": i * 4.0} for i in range(626)]

    hill_id = upload(client, "hill.fit", make_fit(hill))
    bare_id = upload(client, "bare.fit", make_fit(bare))
    ride_id = upload(client, "ride.fit", make_fit(hill, sport=Sport.CYCLING))
    hill, bare, ride = (detail(client, activity_id) for activity_id in (hill_id, bare_id, ride_id))

    assert hill["is_running"] is True
    assert hill["grade_adjusted_pace_s_per_km"] == pytest.approx(181.0, abs=0.5)
    assert hill["aerobic_decoupling_percent"] == pytest.approx(4.8, abs=0.05)
    assert bare["grade_adjusted_pace_s_per_km"] is None
    assert bare["aerobic_decoupling_percent"] is None
    assert (ride["is_running"], ride["pace_s_per_km"]) == (False, pytest.approx(300.0))


def test_activity_detail_gives_estimated_power_once_body_mass_is_set(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    flat = [
        {"t": float(i), "distance": round(i * 10 / 3, 2), "altitude": 10.0, "power": 250}
        for i in range(601)
    ]
    no_altitude = [{"t": float(i), "distance": round(i * 10 / 3, 2)} for i in range(601)]
    run_id = upload(client, "flat.fit", make_fit(flat))
    bare_id = upload(client, "bare.fit", make_fit(no_altitude))
    ride_id = upload(client, "ride.fit", make_fit(flat, sport=Sport.CYCLING))

    before = detail(client, run_id)
    assert (before["avg_power_w"], before["avg_power_w_per_kg"]) == (250.0, None)
    assert before["estimated_power_w"] is None

    Store(tmp_path, connect(tmp_path)).save_athlete_settings(
        AthleteSettings(max_hr=190, resting_hr=50, body_mass_kg=70.0)
    )
    run, bare, ride = (detail(client, activity_id) for activity_id in (run_id, bare_id, ride_id))

    assert run["estimated_power_w"] == pytest.approx(234.0, abs=0.5)
    assert run["estimated_power_w_per_kg"] == pytest.approx(3.34, abs=0.005)
    assert (run["avg_power_w"], run["avg_power_w_per_kg"]) == (
        250.0,
        pytest.approx(3.57, abs=0.005),
    )
    assert bare["estimated_power_w"] is None
    assert bare["avg_power_w"] is None
    assert ride["is_running"] is False


def strip_dynamics(tmp_path, data: bytes) -> Path:
    stream = tmp_path / "streams" / f"{hashlib.sha256(data).hexdigest()}.parquet"
    pl.read_parquet(stream).drop(DYNAMICS_COLUMNS).write_parquet(stream)
    return stream


def test_activity_imported_before_running_dynamics_gets_them_on_first_view(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    fit = make_fit(DYNAMICS_ROWS)
    activity_id = upload(client, "dynamics.fit", fit)
    stream = strip_dynamics(tmp_path, fit)

    assert detail(client, activity_id)["running_dynamics"] == DYNAMICS
    stored = pl.read_parquet(stream)
    assert stored["ground_contact_time"].to_list() == [250.0] * 601
    assert stored["step_length"].to_list() == pytest.approx([1.1] * 601)
    assert list(tmp_path.joinpath("streams").iterdir()) == [stream]
    first = client.get(f"/api/activities/{activity_id}/records").json()[0]
    assert first["vertical_oscillation"] == 85.0


def test_activity_whose_original_no_longer_matches_gets_empty_running_dynamics(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    fit = make_fit(DYNAMICS_ROWS)
    activity_id = upload(client, "dynamics.fit", fit)
    stream = strip_dynamics(tmp_path, fit)
    (tmp_path / "originals" / hashlib.sha256(fit).hexdigest()).write_bytes(
        make_fit(DYNAMICS_ROWS[:-1])
    )

    assert detail(client, activity_id)["running_dynamics"] == NO_DYNAMICS
    stored = pl.read_parquet(stream)
    for column in DYNAMICS_COLUMNS:
        assert stored[column].null_count() == stored.height


GPX = b"""<?xml version="1.0"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Harbour loop</name><type>running</type><trkseg>
    <trkpt lat="55.6700" lon="12.5600"><time>2026-03-01T07:00:00Z</time></trkpt>
    <trkpt lat="55.6710" lon="12.5600"><time>2026-03-01T07:00:30Z</time></trkpt>
    <trkpt lat="55.6720" lon="12.5600"><time>2026-03-01T07:01:00Z</time></trkpt>
  </trkseg></trk>
</gpx>
"""


def test_gpx_activity_is_listed_by_its_track_name(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    upload(client, "run.gpx", GPX)

    [activity] = client.get("/api/activities").json()["items"]

    assert (activity["name"], activity["filename"]) == ("Harbour loop", "run.gpx")


def test_uploaded_zip_is_stored_as_the_file_inside_and_dedupes_against_it(
    tmp_path, steady_run_fit, make_zip
):
    client = TestClient(create_app(data_dir=tmp_path))

    archive = make_zip(("25132893842_ACTIVITY.fit", steady_run_fit))
    response = client.post(
        "/api/activities", files=[("files", ("25132893842.zip", archive, "application/zip"))]
    )
    assert response.status_code == 200
    again = client.post(
        "/api/activities",
        files=[("files", ("run.fit", steady_run_fit, "application/octet-stream"))],
    )
    assert again.json()["results"][0]["status"] == "already_imported"

    store = Store(tmp_path, connect(tmp_path))
    [row] = store.list()
    digest = hashlib.sha256(steady_run_fit).hexdigest()
    assert (row.filename, row.sha256, row.storage_key) == (
        "25132893842_ACTIVITY.fit",
        digest,
        digest,
    )
    assert (tmp_path / "originals" / digest).read_bytes() == steady_run_fit


def test_bulk_export_zip_is_refused_with_a_reason(tmp_path, steady_run_fit, make_zip):
    client = TestClient(create_app(data_dir=tmp_path))

    archive = make_zip(("a.fit", steady_run_fit), ("b.fit", steady_run_fit))
    response = client.post(
        "/api/activities", files=[("files", ("export.zip", archive, "application/zip"))]
    )

    assert response.json()["results"] == [
        {
            "filename": "export.zip",
            "status": "failed",
            "activity_id": None,
            "error": "ZIP holds more than one activity file; extract it and import the files",
        }
    ]
    assert client.get("/api/activities").json()["items"] == []

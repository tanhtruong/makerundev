import hashlib
import json
import re
import sqlite3
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient
from fit_tool.profile.profile_type import Sport
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
    assert table_cells(detail.text, "splits") == [
        *("1", "1.00 km", "5:33", "5:33 /km"),
        *("2", "1.00 km", "5:33", "5:33 /km"),
        *("3", "1.00 km", "5:33", "5:33 /km"),
    ]


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


LAP_ROWS = [{"t": float(i), "distance": i * 3.0} for i in range(601)]
LAPS = [
    {"t": 0.0, "elapsed": 330.0, "distance": 1000.0},
    {"t": 330.0, "elapsed": 270.0, "distance": 800.0},
]
LAP_CELLS = ["1", "5:30", "1.00 km", "5:30 /km", "2", "4:30", "0.80 km", "5:38 /km"]


def table_cells(page: str, name: str) -> list[str]:
    table = re.search(rf'<table class="{name}">.*?<tbody>(.*?)</tbody>', page, re.S)
    assert table is not None
    return [cell.strip() for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", table[1], re.S)]


def test_uploaded_activity_shows_its_laps_with_their_pace(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    fit = make_fit(LAP_ROWS, laps=LAPS)
    client.post("/activities", files=[("files", ("laps.fit", fit, "application/octet-stream"))])
    activity_id = client.get("/api/activities").json()[0]["id"]

    with sqlite3.connect(tmp_path / "makerundev.db") as db:
        stored = json.loads(db.execute("SELECT laps FROM activities").fetchone()[0])
    assert stored == [
        {"start_time": "2026-03-01T07:00:00+00:00", "elapsed_s": 330.0, "distance_m": 1000.0},
        {"start_time": "2026-03-01T07:05:30+00:00", "elapsed_s": 270.0, "distance_m": 800.0},
    ]
    assert table_cells(client.get(f"/activities/{activity_id}").text, "laps") == LAP_CELLS


def test_activity_imported_before_laps_were_stored_gets_them_on_first_view(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    fit = make_fit(LAP_ROWS, laps=LAPS)
    client.post("/activities", files=[("files", ("laps.fit", fit, "application/octet-stream"))])
    activity_id = client.get("/api/activities").json()[0]["id"]
    with sqlite3.connect(tmp_path / "makerundev.db") as db:
        db.execute("UPDATE activities SET laps = NULL")

    assert table_cells(client.get(f"/activities/{activity_id}").text, "laps") == LAP_CELLS
    (tmp_path / "originals" / hashlib.sha256(fit).hexdigest()).unlink()
    assert table_cells(client.get(f"/activities/{activity_id}").text, "laps") == LAP_CELLS


def test_outdoor_activity_shows_its_route_and_treadmill_run_shows_none(
    tmp_path, steady_run_fit, make_fit
):
    client = TestClient(create_app(data_dir=tmp_path))
    treadmill = make_fit(LAP_ROWS)
    for name, fit in (("outdoor.fit", steady_run_fit), ("treadmill.fit", treadmill)):
        client.post("/activities", files=[("files", (name, fit, "application/octet-stream"))])
    ids = {row["filename"]: row["id"] for row in client.get("/api/activities").json()}

    outdoor = client.get(f"/activities/{ids['outdoor.fit']}").text
    assert '<figure class="route">' in outdoor
    polyline = re.search(r'<polyline points="([^"]+)"', outdoor)
    assert polyline is not None
    assert len(polyline[1].split()) > 2
    assert outdoor.index('<figure class="route">') < outdoor.index("Pace over distance")

    indoor = client.get(f"/activities/{ids['treadmill.fit']}").text
    assert '<figure class="route">' not in indoor
    assert "<polyline" not in indoor


def test_pages_link_icons_that_are_served(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))

    index = client.get("/").text
    for name in ("favicon-light.png", "favicon-dark.png", "apple-touch-icon.png"):
        assert f"/static/{name}" in index
        icon = client.get(f"/static/{name}")
        assert icon.status_code == 200
        assert icon.headers["content-type"] == "image/png"


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
DYNAMICS_TILES = {
    "Ground contact": "250 ms",
    "Vertical oscillation": "8.5 cm",
    "Step length": "1.10 m",
}


def stats(page: str) -> dict[str, str]:
    block = re.search(r'<dl class="stats">(.*?)</dl>', page, re.S)
    assert block is not None
    tiles = re.findall(r"<dt>(.*?)</dt><dd>(.*?)</dd>", block[1])
    return {name: " ".join(re.sub(r"<[^>]+>", " ", value).split()) for name, value in tiles}


def dynamics_tiles(page: str) -> dict[str, str]:
    return {name: value for name, value in stats(page).items() if name in DYNAMICS_TILES}


def upload(client: TestClient, filename: str, data: bytes) -> int:
    client.post("/activities", files=[("files", (filename, data, "application/octet-stream"))])
    activity_id: int = next(
        row["id"] for row in client.get("/api/activities").json() if row["filename"] == filename
    )
    return activity_id


def test_activity_page_shows_grade_adjusted_pace_and_decoupling_for_runs_only(tmp_path, make_fit):
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
    hill_stats, bare_stats, ride_stats = (
        stats(client.get(f"/activities/{activity_id}").text)
        for activity_id in (hill_id, bare_id, ride_id)
    )

    assert hill_stats["Grade-adjusted pace"] == "3:01 /km"
    assert hill_stats["Aerobic decoupling"] == "+4.8%"
    assert bare_stats["Grade-adjusted pace"] == "-"
    assert bare_stats["Aerobic decoupling"] == "-"
    assert ride_stats["Pace"] == "5:00 /km"
    assert "Grade-adjusted pace" not in ride_stats
    assert "Aerobic decoupling" not in ride_stats


def test_activity_page_shows_estimated_power_once_body_mass_is_set(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    flat = [
        {"t": float(i), "distance": round(i * 10 / 3, 2), "altitude": 10.0, "power": 250}
        for i in range(601)
    ]
    no_altitude = [{"t": float(i), "distance": round(i * 10 / 3, 2)} for i in range(601)]
    run_id = upload(client, "flat.fit", make_fit(flat))
    bare_id = upload(client, "bare.fit", make_fit(no_altitude))
    ride_id = upload(client, "ride.fit", make_fit(flat, sport=Sport.CYCLING))

    before = stats(client.get(f"/activities/{run_id}").text)
    assert before["Avg power"] == "250 W"
    assert "Estimated power" not in before

    Store(tmp_path, connect(tmp_path)).save_athlete_settings(
        AthleteSettings(max_hr=190, resting_hr=50, body_mass_kg=70.0)
    )
    run_stats, bare_stats, ride_stats = (
        stats(client.get(f"/activities/{activity_id}").text)
        for activity_id in (run_id, bare_id, ride_id)
    )

    assert run_stats["Estimated power"] == "234 W 3.34 W/kg"
    assert run_stats["Avg power"] == "250 W 3.57 W/kg"
    assert bare_stats["Estimated power"] == "-"
    assert "Avg power" not in bare_stats
    assert "Estimated power" not in ride_stats


def strip_dynamics(tmp_path, data: bytes) -> Path:
    stream = tmp_path / "streams" / f"{hashlib.sha256(data).hexdigest()}.parquet"
    pl.read_parquet(stream).drop(DYNAMICS_COLUMNS).write_parquet(stream)
    return stream


def test_activity_page_shows_running_dynamics_averages(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    activity_id = upload(client, "dynamics.fit", make_fit(DYNAMICS_ROWS))

    assert dynamics_tiles(client.get(f"/activities/{activity_id}").text) == DYNAMICS_TILES


def test_activity_imported_before_running_dynamics_gets_them_on_first_view(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    fit = make_fit(DYNAMICS_ROWS)
    activity_id = upload(client, "dynamics.fit", fit)
    stream = strip_dynamics(tmp_path, fit)

    assert dynamics_tiles(client.get(f"/activities/{activity_id}").text) == DYNAMICS_TILES
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

    assert dynamics_tiles(client.get(f"/activities/{activity_id}").text) == {}
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

    [activity] = client.get("/api/activities").json()

    assert (activity["name"], activity["filename"]) == ("Harbour loop", "run.gpx")
    assert table_cells(client.get("/").text, "activities")[1] == "Harbour loop"


def test_gpx_activity_shows_no_running_dynamics_and_is_not_rewritten(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    activity_id = upload(client, "run.gpx", GPX)
    stream = strip_dynamics(tmp_path, GPX)

    page = client.get(f"/activities/{activity_id}").text

    assert "Distance" in stats(page)
    assert dynamics_tiles(page) == {}
    assert not set(DYNAMICS_COLUMNS) & set(pl.read_parquet(stream).columns)


def test_uploaded_zip_is_stored_as_the_file_inside_and_dedupes_against_it(
    tmp_path, steady_run_fit, make_zip
):
    client = TestClient(create_app(data_dir=tmp_path))

    archive = make_zip(("25132893842_ACTIVITY.fit", steady_run_fit))
    response = client.post(
        "/activities", files=[("files", ("25132893842.zip", archive, "application/zip"))]
    )
    assert response.status_code == 200
    again = client.post(
        "/activities", files=[("files", ("run.fit", steady_run_fit, "application/octet-stream"))]
    )
    assert "run.fit: already imported" in again.text

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
        "/activities", files=[("files", ("export.zip", archive, "application/zip"))]
    )

    assert response.status_code == 400
    assert "export.zip: ZIP holds more than one activity file" in response.text
    assert client.get("/api/activities").json() == []

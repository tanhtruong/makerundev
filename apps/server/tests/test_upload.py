import hashlib
import json
import re
import sqlite3

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

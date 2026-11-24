import datetime as dt
from pathlib import Path

import openapi
import pytest
from fastapi.testclient import TestClient
from fit_tool.profile.profile_type import Sport as FitSport
from fit_tool.profile.profile_type import SubSport
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
    assert listed(client, sort="start_time") == [
        "sun.fit",
        "mon.fit",
        "tue.fit",
        "tie-a.fit",
        "tie-b.fit",
    ]
    first = client.get("/api/activities").json()["items"][0]
    assert (first["start_time"], first["avg_heart_rate_bpm"]) == ("2026-03-04T07:00:00Z", 140.0)


@pytest.mark.parametrize("params", [{"limit": 201}, {"limit": 0}, {"offset": -1}])
def test_a_page_outside_the_limits_is_refused(client, params):
    response = client.get("/api/activities", params=params)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", next(iter(params))]


def steady(
    speed: float, seconds: int, hr: int | None = 140, climb: float = 0.0
) -> list[dict[str, float]]:
    steps = seconds // 10
    rows = []
    for i in range(steps + 1):
        row = {"t": i * 10.0, "distance": i * 10.0 * speed, "speed": speed}
        row["altitude"] = 10.0 + climb * i / steps
        if hr is not None:
            row["hr"] = hr
        rows.append(row)
    return rows


def upload(client: TestClient, filename: str, data: bytes) -> None:
    response = client.post("/api/activities", files=[("files", (filename, data))])
    assert response.json()["results"][0]["status"] == "imported"


def listed(client: TestClient, **params: object) -> list[str]:
    response = client.get("/api/activities", params=params)
    assert response.status_code == 200, response.json()
    return [activity["filename"] for activity in response.json()["items"]]


NAMED_GPX = b"""<?xml version="1.0"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Harbour loop</name><type>running</type><trkseg>
    <trkpt lat="55.6700" lon="12.5600"><time>2026-03-20T07:00:00Z</time></trkpt>
    <trkpt lat="55.6710" lon="12.5600"><time>2026-03-20T07:00:30Z</time></trkpt>
  </trkseg></trk>
</gpx>
"""


def test_filters_combine_and_page_with_the_filtered_total(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    library = [
        ("harbour-10k.fit", 10, FitSport.RUNNING, SubSport.GENERIC, 10_000),
        ("harbour-5k.fit", 11, FitSport.RUNNING, SubSport.GENERIC, 5_000),
        ("harbour-ride.fit", 12, FitSport.CYCLING, SubSport.GENERIC, 12_000),
        ("harbour-trail.fit", 13, FitSport.RUNNING, SubSport.TRAIL, 12_000),
        ("park-12k.fit", 14, FitSport.RUNNING, SubSport.GENERIC, 12_000),
        ("HARBOUR-15k.fit", 15, FitSport.RUNNING, SubSport.GENERIC, 15_000),
        ("harbour-hike.fit", 16, FitSport.HIKING, SubSport.GENERIC, 8_000),
    ]
    for filename, day, sport, sub_sport, metres in library:
        rows = steady(4.0, metres // 4)
        upload(client, filename, make_fit(rows, sport, sub_sport, start=at(day)))
    upload(client, "named.gpx", NAMED_GPX)
    wanted = {
        "q": "harbour",
        "sport": ["running", "trail_running"],
        "min_distance_m": 6_000,
        "max_distance_m": 14_000,
        "limit": 1,
    }

    pages = [client.get("/api/activities", params=wanted | {"offset": n}).json() for n in (0, 1)]

    assert [[a["filename"] for a in page["items"]] for page in pages] == [
        ["harbour-trail.fit"],
        ["harbour-10k.fit"],
    ]
    assert [page["total"] for page in pages] == [2, 2]
    assert listed(client, q="HARBOUR-15") == ["HARBOUR-15k.fit"]
    assert listed(client, q="loop") == ["named.gpx"]
    assert listed(client, q="  ") == listed(client)


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


def test_from_and_to_are_whole_local_days_in_the_athletes_timezone(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    assert client.put("/api/settings", json=BASE_SETTINGS).status_code == 200
    starts = {
        "feb-28-late.fit": dt.datetime(2026, 2, 28, 22, 30, tzinfo=dt.UTC),
        "mar-1-early.fit": dt.datetime(2026, 2, 28, 23, 30, tzinfo=dt.UTC),
        "mar-1-late.fit": dt.datetime(2026, 3, 1, 22, 30, tzinfo=dt.UTC),
        "mar-2-early.fit": dt.datetime(2026, 3, 1, 23, 30, tzinfo=dt.UTC),
    }
    for filename, start in starts.items():
        upload(client, filename, make_fit(steady(3.0, 600), start=start))

    one_day = listed(client, **{"from": "2026-03-01", "to": "2026-03-01"})

    assert one_day == ["mar-1-late.fit", "mar-1-early.fit"]
    assert listed(client, **{"from": "2026-03-02"}) == ["mar-2-early.fit"]
    assert listed(client, to="2026-02-28") == ["feb-28-late.fit"]
    assert len(listed(client, **{"from": "0001-01-01", "to": "9999-12-31"})) == 4


def test_search_folds_any_letter_case_and_matches_wildcards_literally(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    for day, filename in enumerate(["Đà Lạt tempo.fit", "100% effort.fit", "easy_run.fit"], 1):
        upload(client, filename, make_fit(steady(3.0, 600), start=at(day)))

    assert listed(client, q="đà lạt") == ["Đà Lạt tempo.fit"]
    assert listed(client, q="%") == ["100% effort.fit"]
    assert listed(client, q="_") == ["easy_run.fit"]


@pytest.fixture
def varied(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    assert client.put("/api/settings", json=BASE_SETTINGS).status_code == 200
    runs = [
        ("x.fit", 2, steady(2.5, 600, hr=160, climb=60)),
        ("y.fit", 4, steady(4.0, 1500, hr=130, climb=40)),
        ("z.fit", 1, steady(3.0, 3000, hr=145, climb=20)),
        ("n.fit", 3, steady(1.0, 1300, hr=None)),
    ]
    for filename, day, rows in runs:
        upload(client, filename, make_fit(rows, start=at(day)))
    return client


@pytest.mark.parametrize(
    ("key", "ascending", "descending"),
    [
        ("start_time", "zxny", "ynxz"),
        ("distance_m", "nxyz", "zyxn"),
        ("moving_s", "xnyz", "zynx"),
        ("pace_s_per_km", "yzxn", "nxzy"),
        ("avg_heart_rate_bpm", "yzxn", "xzyn"),
        ("elevation_gain_m", "nzyx", "xyzn"),
        ("trimp", "xyzn", "zyxn"),
    ],
)
def test_sorting_orders_by_the_key_either_way_with_missing_values_last(
    varied, key, ascending, descending
):
    def order(sort: str) -> str:
        return "".join(name[0] for name in listed(varied, sort=sort))

    assert (order(key), order(f"-{key}")) == (ascending, descending)


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"from": "2026-03-02", "to": "2026-03-01"}, "from"),
        ({"min_distance_m": 5000, "max_distance_m": 4000}, "min_distance_m"),
        ({"sport": "jogging"}, "sport"),
        ({"sort": "-name"}, "sort"),
        ({"q": "x" * 101}, "q"),
    ],
)
def test_an_impossible_filter_is_refused(client, params, field):
    response = client.get("/api/activities", params=params)

    assert response.status_code == 422
    assert [error["loc"][:2] for error in response.json()["detail"]] == [["query", field]]

import datetime as dt
import itertools
import re
import sqlite3

import pytest
from fastapi.testclient import TestClient
from fit_tool.profile.profile_type import Sport, SubSport
from makerundev.metrics import training_load
from makerundev_server import create_app
from makerundev_server.charts import WIDTH, load_chart, zone_bars
from makerundev_server.db import ActivityRow
from makerundev_server.training import Day, load_view

SETTINGS = {
    "max_hr": "190",
    "resting_hr": "50",
    "trimp_coefficients": "male",
    "timezone": "Europe/Copenhagen",
    "zone_model": "max_hr_percent",
    "zone_2": "60",
    "zone_3": "70",
    "zone_4": "80",
    "zone_5": "90",
}


def run(start: str, trimp: float | None) -> ActivityRow:
    return ActivityRow(start_time=dt.datetime.fromisoformat(start), trimp=trimp)


def client_with(tmp_path, *files: tuple[str, bytes], settings: bool = True) -> TestClient:
    client = TestClient(create_app(data_dir=tmp_path))
    if settings:
        client.post("/settings", data=SETTINGS)
    for name, data in files:
        client.post("/activities", files=[("files", (name, data, "application/octet-stream"))])
    return client


def steady(make_fit, metres: float, seconds: int, day: int, **kwargs) -> bytes:
    rows = [{"t": float(i), "distance": metres * i / seconds} for i in range(seconds + 1)]
    return make_fit(rows, start=dt.datetime(2026, 3, day, 7, tzinfo=dt.UTC), **kwargs)


def performance(client: TestClient) -> str:
    page = client.get("/load").text
    found = re.search(r'<section class="performance".*?</section>', page, re.S)
    assert found is not None
    return " ".join(re.sub(r"<[^>]+>", " ", found.group()).split())


def ids(client: TestClient) -> dict[str, int]:
    return {row["filename"]: row["id"] for row in client.get("/api/activities").json()["items"]}


@pytest.fixture
def march_10(monkeypatch):
    monkeypatch.setattr("makerundev_server.app.today_in", lambda _timezone: dt.date(2026, 3, 10))


def test_current_vdot_and_critical_speed_come_from_the_best_qualifying_efforts(
    tmp_path, make_fit, march_10
):
    client = client_with(
        tmp_path,
        ("tempo.fit", steady(make_fit, 5000, 1250, 5)),
        ("reps.fit", steady(make_fit, 1000, 200, 3)),
        ("strides.fit", steady(make_fit, 400, 60, 8)),
        ("treadmill.fit", steady(make_fit, 5000, 1000, 7, sub_sport=SubSport.TREADMILL)),
    )

    text = performance(client)

    assert "VDOT 52.2 1 km in 3:20, reps.fit, 3 Mar" in text
    assert f'<a href="/activities/{ids(client)["reps.fit"]}">' in client.get("/load").text
    assert "Critical speed 4:32 /km D\u2032 213 m" in text
    assert (
        "Critical speed fitted on 1 km in 3:20, reps.fit, 3 Mar 1 mile in 6:42, tempo.fit, 5 Mar"
        " 3 km in 12:30, tempo.fit, 5 Mar" in text
    )


def test_excluding_the_source_activity_moves_vdot_to_the_next_best_effort(
    tmp_path, make_fit, march_10
):
    client = client_with(
        tmp_path,
        ("tempo.fit", steady(make_fit, 5000, 1250, 5)),
        ("reps.fit", steady(make_fit, 1000, 200, 3)),
    )
    reps = ids(client)["reps.fit"]

    response = client.post(
        f"/activities/{reps}/exclusion", data={"excluded": "true"}, follow_redirects=False
    )

    assert (response.status_code, response.headers["location"]) == (303, f"/activities/{reps}")
    text = performance(client)
    assert "VDOT 47.5 5 km in 20:50, tempo.fit, 5 Mar" in text
    assert "1 activity in the last 6 weeks is excluded" in text


def test_excluding_through_the_api_moves_vdot_and_including_moves_it_back(
    tmp_path, make_fit, march_10
):
    client = client_with(
        tmp_path,
        ("tempo.fit", steady(make_fit, 5000, 1250, 5)),
        ("reps.fit", steady(make_fit, 1000, 200, 3)),
    )
    reps = ids(client)["reps.fit"]

    response = client.put(f"/api/activities/{reps}/exclusion", json={"excluded": True})

    assert (response.status_code, response.json()) == (200, {"excluded": True})
    assert client.get(f"/api/activities/{reps}").json()["excluded_from_performance"] is True
    assert "VDOT 47.5 5 km in 20:50, tempo.fit, 5 Mar" in performance(client)

    client.put(f"/api/activities/{reps}/exclusion", json={"excluded": False})

    assert client.get(f"/api/activities/{reps}").json()["excluded_from_performance"] is False
    assert "VDOT 52.2 1 km in 3:20, reps.fit, 3 Mar" in performance(client)


def test_a_sport_that_does_not_count_cannot_be_excluded(tmp_path, make_fit):
    client = client_with(
        tmp_path, ("ride.fit", steady(make_fit, 5000, 600, 3, sport=Sport.CYCLING))
    )
    ride = ids(client)["ride.fit"]

    response = client.put(f"/api/activities/{ride}/exclusion", json={"excluded": True})

    assert (response.status_code, response.json()) == (
        409,
        {"detail": "activity does not count towards performance"},
    )
    assert client.get(f"/api/activities/{ride}").json()["excluded_from_performance"] is False


def test_an_activity_stored_without_efforts_gets_them_when_the_load_page_opens(
    tmp_path, make_fit, march_10
):
    client = client_with(tmp_path, ("reps.fit", steady(make_fit, 1000, 200, 3)))
    with sqlite3.connect(tmp_path / "makerundev.db") as database:
        database.execute("UPDATE activities SET best_efforts = NULL")

    assert "VDOT 52.2 1 km in 3:20, reps.fit, 3 Mar" in performance(client)


def test_daily_load_is_bucketed_by_local_date_and_runs_through_today():
    rows = [
        run("2026-03-01T07:00:00+00:00", 50.0),
        run("2026-03-01T12:00:00+00:00", 20.0),
        run("2026-03-01T23:30:00+00:00", 30.0),
        run("2026-03-03T07:00:00+00:00", None),
    ]

    view = load_view(rows, "Europe/Copenhagen", dt.date(2026, 3, 10), days=None)

    assert view is not None
    expected = training_load(
        {dt.date(2026, 3, 1): 70.0, dt.date(2026, 3, 2): 30.0},
        start=dt.date(2026, 3, 1),
        end=dt.date(2026, 3, 10),
    )
    assert [day.date for day in view.days] == expected["date"].to_list()
    assert [day.fitness for day in view.days] == pytest.approx(expected["fitness"].to_list())
    assert view.today.date == dt.date(2026, 3, 10)
    assert (view.activities, view.without_heart_rate) == (4, 1)


def test_a_range_keeps_the_history_before_it_in_fitness():
    rows = [run("2026-01-01T07:00:00+00:00", 100.0), run("2026-03-09T07:00:00+00:00", 40.0)]

    whole = load_view(rows, "UTC", dt.date(2026, 3, 10), days=None)
    recent = load_view(rows, "UTC", dt.date(2026, 3, 10), days=7)

    assert whole is not None and recent is not None
    assert recent.days[0].date == dt.date(2026, 3, 4)
    assert len(recent.days) == 7
    assert recent.today == whole.today
    assert recent.days[0].fitness > 0
    assert recent.activities == 1


def test_load_page_opens_before_settings_are_saved(tmp_path, steady_run_fit):
    client = client_with(tmp_path, ("run.fit", steady_run_fit), settings=False)

    assert client.get("/load").status_code == 200


def test_load_page_shows_charts_ranges_and_activities_without_heart_rate(
    tmp_path, steady_run_fit, make_fit, monkeypatch
):
    monkeypatch.setattr("makerundev_server.app.today_in", lambda _timezone: dt.date(2026, 12, 1))
    no_heart_rate = make_fit([{"t": float(i), "distance": i * 3.0} for i in range(301)])
    client = client_with(tmp_path, ("run.fit", steady_run_fit), ("no-hr.fit", no_heart_rate))

    page = client.get("/load?days=all")

    assert page.status_code == 200
    assert 'href="/load?days=all" aria-current="page"' in page.text
    for days in ("90", "180", "365"):
        assert f'href="/load?days={days}"' in page.text
    assert 'aria-label="Fitness and fatigue by day"' in page.text
    assert 'aria-label="Form by day"' in page.text
    assert "1 activity in this range had no heart rate, so it counts as 0." in page.text
    assert "2026-03-01: fitness" in page.text


def test_unknown_range_falls_back_to_180_days(tmp_path, steady_run_fit):
    client = client_with(tmp_path, ("run.fit", steady_run_fit))

    page = client.get("/load?days=7")

    assert 'href="/load?days=180" aria-current="page"' in page.text


def test_activity_page_shows_time_in_zones_and_trimp(tmp_path, steady_run_fit):
    client = client_with(tmp_path, ("run.fit", steady_run_fit))
    activity = client.get("/api/activities").json()["items"][0]

    page = client.get(f"/activities/{activity['id']}")

    assert activity["trimp"] == pytest.approx(23.56, abs=0.01)
    assert "<dt>TRIMP</dt><dd>24</dd>" in page.text
    assert "Zone 3 <span>133-151 bpm</span>" in page.text
    assert "Zone 1 <span>under 114 bpm</span>" in page.text
    assert "Zone 5 <span>171 bpm and up</span>" in page.text
    assert re.search(r"Zone 3 <span>133-151 bpm</span>(?:(?!</tr>).)*>100%<", page.text, re.S)


def test_heart_rate_reserve_zones_start_from_resting_heart_rate(tmp_path, steady_run_fit):
    client = client_with(tmp_path, ("run.fit", steady_run_fit), settings=False)
    client.post("/settings", data=SETTINGS | {"zone_model": "hr_reserve_percent"})
    activity = client.get("/api/activities").json()["items"][0]

    page = client.get(f"/activities/{activity['id']}")

    assert "Zone 1 <span>under 134 bpm</span>" in page.text
    assert "Zone 4 <span>162-175 bpm</span>" in page.text
    assert re.search(r"Zone 2 <span>134-147 bpm</span>(?:(?!</tr>).)*>100%<", page.text, re.S)


def test_activity_times_show_in_the_settings_timezone(tmp_path, steady_run_fit):
    client = client_with(tmp_path, ("run.fit", steady_run_fit))
    activity = client.get("/api/activities").json()["items"][0]

    assert "2026-03-01 08:00 CET" in client.get(f"/activities/{activity['id']}").text


def test_zone_labels_name_the_whole_bpm_values_in_each_zone():
    bars = zone_bars([60.0, 60.0, 0.0], [111.0, 134.1])

    assert [bar.bpm for bar in bars] == ["under 111 bpm", "111-134 bpm", "135 bpm and up"]
    assert [bar.share for bar in bars] == [0.5, 0.5, 0.0]


def test_a_single_day_draws_flat_lines_and_one_hover_target():
    chart = load_chart([Day(dt.date(2026, 3, 1), 40.0, 1.0, 5.0, 0.0)])

    assert chart.fitness.path.startswith("M0,") and f" L{WIDTH}," in chart.fitness.path
    assert [(hit.x, hit.width) for hit in chart.hits] == [(0.0, WIDTH)]
    assert chart.load_top == 10.0


def test_hover_targets_tile_the_chart_without_gaps():
    days = [Day(dt.date(2026, 3, 1) + dt.timedelta(days=i), 10.0, i, i, 0.0) for i in range(90)]

    hits = load_chart(days).hits

    assert hits[0].x == 0.0
    assert sum(hit.width for hit in hits) == pytest.approx(WIDTH)
    for left, right in itertools.pairwise(hits):
        assert right.x == pytest.approx(left.x + left.width)

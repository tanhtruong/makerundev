import datetime as dt
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fit_tool.profile.profile_type import Sport, SubSport
from makerundev.metrics import training_load
from makerundev_server import create_app
from settings_payload import SETTINGS

MARCH_10 = dt.datetime(2026, 3, 10, 12, tzinfo=dt.UTC)


def client_with(
    tmp_path, *files: tuple[str, bytes], settings: bool = True, now: dt.datetime = MARCH_10
) -> TestClient:
    client = TestClient(create_app(data_dir=tmp_path, clock=lambda: now))
    if settings:
        client.put("/api/settings", json=SETTINGS)
    for name, data in files:
        client.post("/api/activities", files=[("files", (name, data, "application/octet-stream"))])
    return client


def steady(make_fit, metres: float, seconds: int, day: int, **kwargs) -> bytes:
    rows = [{"t": float(i), "distance": metres * i / seconds} for i in range(seconds + 1)]
    return make_fit(rows, start=dt.datetime(2026, 3, day, 7, tzinfo=dt.UTC), **kwargs)


def performance(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/training-load")
    assert response.status_code == 200
    found: dict[str, Any] = response.json()["performance"]
    return found


def effort(activity_id: int, name: str, day: int, metres: float, seconds: float) -> dict[str, Any]:
    return {
        "activity_id": activity_id,
        "activity_name": name,
        "start_time": f"2026-03-{day:02d}T07:00:00Z",
        "date": f"2026-03-{day:02d}",
        "distance_m": metres,
        "elapsed_s": pytest.approx(seconds, abs=0.5),
    }


def ids(client: TestClient) -> dict[str, int]:
    return {row["filename"]: row["id"] for row in client.get("/api/activities").json()["items"]}


def hard_ride(make_fit) -> bytes:
    rows = [{"t": float(i), "distance": 8.0 * i, "hr": 180} for i in range(1801)]
    return make_fit(rows, sport=Sport.CYCLING, start=dt.datetime(2026, 3, 1, 7, tzinfo=dt.UTC))


def test_training_load_api_returns_days_weeks_bounds_and_current_performance(tmp_path, make_fit):
    client = client_with(
        tmp_path,
        ("ride.fit", hard_ride(make_fit)),
        ("reps.fit", steady(make_fit, 1000, 200, 3)),
        ("tempo.fit", steady(make_fit, 5000, 1250, 5)),
    )
    trimp = next(
        row["trimp"]
        for row in client.get("/api/activities").json()["items"]
        if row["filename"] == "ride.fit"
    )
    activity = ids(client)

    response = client.get("/api/training-load")

    assert response.status_code == 200
    body = response.json()
    assert body["settings_set"] is True
    load = body["load"]

    def day(date: str, load: float, after: int) -> dict[str, object]:
        fitness = trimp / 42 * (41 / 42) ** after
        fatigue = trimp / 7 * (6 / 7) ** after
        form = (
            0.0
            if after == 0
            else trimp / 42 * (41 / 42) ** (after - 1) - trimp / 7 * (6 / 7) ** (after - 1)
        )
        return {
            "date": date,
            "trimp": load,
            "fitness": pytest.approx(fitness),
            "fatigue": pytest.approx(fatigue),
            "form": pytest.approx(form),
        }

    assert len(load["days"]) == 10
    assert load["days"][0] == day("2026-03-01", trimp, 0)
    assert load["today"] == day("2026-03-10", 0.0, 9)
    assert load["days"][-1] == load["today"]

    def week(ending: str, load: float, after: int) -> dict[str, object]:
        row = day(ending, load, after)
        return {"week_ending": row.pop("date"), **row}

    assert load["weeks"] == [week("2026-03-10", 0.0, 9), week("2026-03-03", trimp, 2)]
    assert load["bounds"] == {
        "fitness_fatigue": {"low": 0.0, "high": pytest.approx(trimp / 7)},
        "form": {"low": pytest.approx(trimp / 42 - trimp / 7), "high": 5.0},
    }
    assert (load["activities"], load["without_heart_rate"]) == (3, 2)

    performance = body["performance"]
    assert performance["vdot"] == pytest.approx(52.2, abs=0.05)
    reps = {
        "activity_id": activity["reps.fit"],
        "activity_name": "reps.fit",
        "start_time": "2026-03-03T07:00:00Z",
        "date": "2026-03-03",
        "distance_m": 1000.0,
        "elapsed_s": 200.0,
    }
    assert performance["vdot_effort"] == reps
    tempo = {
        "activity_id": activity["tempo.fit"],
        "activity_name": "tempo.fit",
        "start_time": "2026-03-05T07:00:00Z",
        "date": "2026-03-05",
    }
    assert performance["fitted"] == [
        reps,
        {**tempo, "distance_m": 1609.344, "elapsed_s": pytest.approx(402.336, abs=0.5)},
        {**tempo, "distance_m": 3000.0, "elapsed_s": 750.0},
    ]
    critical_speed = performance["critical_speed"]
    assert critical_speed["pace_s_per_km"] == pytest.approx(272.0, abs=0.5)
    assert critical_speed["speed_mps"] == pytest.approx(1000 / critical_speed["pace_s_per_km"])
    assert critical_speed["d_prime_m"] == pytest.approx(213.0, abs=0.5)
    assert (performance["critical_speed_reason"], performance["excluded"]) == (None, 0)


def test_current_vdot_and_critical_speed_come_from_the_best_qualifying_efforts(tmp_path, make_fit):
    client = client_with(
        tmp_path,
        ("tempo.fit", steady(make_fit, 5000, 1250, 5)),
        ("reps.fit", steady(make_fit, 1000, 200, 3)),
        ("strides.fit", steady(make_fit, 400, 60, 8)),
        ("treadmill.fit", steady(make_fit, 5000, 1000, 7, sub_sport=SubSport.TREADMILL)),
    )

    found = performance(client)

    activity = ids(client)
    reps, tempo = activity["reps.fit"], activity["tempo.fit"]
    assert found["vdot"] == pytest.approx(52.2, abs=0.05)
    assert found["vdot_effort"] == effort(reps, "reps.fit", 3, 1000.0, 200.0)
    assert found["critical_speed"]["pace_s_per_km"] == pytest.approx(272.0, abs=0.5)
    assert found["critical_speed"]["d_prime_m"] == pytest.approx(213.0, abs=0.5)
    assert found["fitted"] == [
        effort(reps, "reps.fit", 3, 1000.0, 200.0),
        effort(tempo, "tempo.fit", 5, 1609.344, 402.336),
        effort(tempo, "tempo.fit", 5, 3000.0, 750.0),
    ]


def test_an_effort_is_dated_by_the_local_day_it_started(tmp_path, make_fit):
    rows = [{"t": float(i), "distance": 5.0 * i} for i in range(201)]
    late = make_fit(rows, start=dt.datetime(2026, 3, 3, 23, 30, tzinfo=dt.UTC))
    client = client_with(tmp_path, ("late.fit", late))

    found = performance(client)

    assert found["vdot_effort"]["start_time"] == "2026-03-03T23:30:00Z"
    assert found["vdot_effort"]["date"] == "2026-03-04"


def test_excluding_through_the_api_moves_vdot_and_including_moves_it_back(tmp_path, make_fit):
    client = client_with(
        tmp_path,
        ("tempo.fit", steady(make_fit, 5000, 1250, 5)),
        ("reps.fit", steady(make_fit, 1000, 200, 3)),
    )
    reps = ids(client)["reps.fit"]

    response = client.put(f"/api/activities/{reps}/exclusion", json={"excluded": True})

    assert (response.status_code, response.json()) == (200, {"excluded": True})
    assert client.get(f"/api/activities/{reps}").json()["excluded_from_performance"] is True
    found = performance(client)
    assert found["vdot_effort"]["activity_name"] == "tempo.fit"
    assert found["excluded"] == 1

    client.put(f"/api/activities/{reps}/exclusion", json={"excluded": False})

    assert client.get(f"/api/activities/{reps}").json()["excluded_from_performance"] is False
    assert performance(client)["vdot_effort"]["activity_name"] == "reps.fit"


def test_training_load_api_refuses_an_unknown_range(tmp_path):
    client = client_with(tmp_path)

    assert client.get("/api/training-load?days=7").status_code == 422


def test_training_load_api_thins_a_long_history_and_keeps_weeks_from_every_day(tmp_path, make_fit):
    old = make_fit(
        [{"t": float(i), "distance": 3.0 * i} for i in range(301)],
        start=dt.datetime(2023, 1, 1, 7, tzinfo=dt.UTC),
    )
    client = client_with(tmp_path, ("old.fit", old), ("reps.fit", steady(make_fit, 1000, 200, 3)))

    load = client.get("/api/training-load?days=all").json()["load"]
    year = client.get("/api/training-load?days=365").json()["load"]
    default = client.get("/api/training-load").json()["load"]

    dates = [dt.date.fromisoformat(day["date"]) for day in load["days"]]
    assert len(dates) == 1000
    assert (dates[0], dates[-1]) == (dt.date(2023, 1, 1), dt.date(2026, 3, 10))
    assert dates == sorted(set(dates))
    assert load["today"]["date"] == "2026-03-10"
    assert len(load["weeks"]) == 167
    assert load["weeks"][-1]["week_ending"] == "2023-01-03"
    assert (len(year["days"]), len(default["days"])) == (365, 180)


def test_training_load_api_keeps_a_minimum_scale_when_no_run_has_heart_rate(tmp_path, make_fit):
    client = client_with(tmp_path, ("reps.fit", steady(make_fit, 1000, 200, 3)))

    load = client.get("/api/training-load").json()["load"]

    assert load["bounds"] == {
        "fitness_fatigue": {"low": 0.0, "high": 10.0},
        "form": {"low": -5.0, "high": 5.0},
    }


def test_training_load_api_answers_before_settings_and_before_any_activity(tmp_path, make_fit):
    unset = client_with(
        tmp_path / "unset", ("reps.fit", steady(make_fit, 1000, 200, 3)), settings=False
    )
    empty = client_with(tmp_path / "empty")

    before_settings = unset.get("/api/training-load").json()
    no_activities = empty.get("/api/training-load").json()

    assert (before_settings["settings_set"], before_settings["load"]) == (False, None)
    performance = before_settings["performance"]
    assert performance["vdot"] == pytest.approx(52.2, abs=0.05)
    assert (performance["critical_speed"], performance["critical_speed_reason"]) == (
        None,
        "too_few_efforts",
    )
    assert no_activities == {"settings_set": True, "load": None, "performance": None}


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


def hr_run(make_fit, start: str, hr: int | None = 150) -> bytes:
    rows = [{"t": float(i), "distance": 3.0 * i, **({"hr": hr} if hr else {})} for i in range(601)]
    return make_fit(rows, start=dt.datetime.fromisoformat(start))


def trimps(client: TestClient) -> dict[str, float]:
    return {row["filename"]: row["trimp"] for row in client.get("/api/activities").json()["items"]}


def test_daily_load_is_bucketed_by_local_date_and_runs_through_today(tmp_path, make_fit):
    client = client_with(
        tmp_path,
        ("morning.fit", hr_run(make_fit, "2026-03-01T07:00:00+00:00", hr=150)),
        ("noon.fit", hr_run(make_fit, "2026-03-01T12:00:00+00:00", hr=160)),
        ("late.fit", hr_run(make_fit, "2026-03-01T23:30:00+00:00", hr=170)),
        ("no-hr.fit", hr_run(make_fit, "2026-03-03T07:00:00+00:00", hr=None)),
        now=dt.datetime(2026, 3, 9, 23, 30, tzinfo=dt.UTC),
    )
    trimp = trimps(client)

    load = client.get("/api/training-load?days=all").json()["load"]

    expected = training_load(
        {
            dt.date(2026, 3, 1): trimp["morning.fit"] + trimp["noon.fit"],
            dt.date(2026, 3, 2): trimp["late.fit"],
        },
        start=dt.date(2026, 3, 1),
        end=dt.date(2026, 3, 10),
    )
    assert [day["date"] for day in load["days"]] == [
        date.isoformat() for date in expected["date"].to_list()
    ]
    assert [day["trimp"] for day in load["days"]] == pytest.approx(expected["load"].to_list())
    assert [day["fitness"] for day in load["days"]] == pytest.approx(expected["fitness"].to_list())
    assert load["today"]["date"] == "2026-03-10"
    assert (load["activities"], load["without_heart_rate"]) == (4, 1)


def test_a_range_keeps_the_history_before_it_in_fitness(tmp_path, make_fit):
    client = client_with(
        tmp_path,
        ("old.fit", hr_run(make_fit, "2025-11-01T07:00:00+00:00")),
        ("recent.fit", hr_run(make_fit, "2026-03-09T07:00:00+00:00")),
    )

    whole = client.get("/api/training-load?days=all").json()["load"]
    recent = client.get("/api/training-load?days=90").json()["load"]

    assert recent["days"][0]["date"] == "2025-12-11"
    assert len(recent["days"]) == 90
    assert recent["today"] == whole["today"]
    assert recent["days"][0]["fitness"] > 0
    assert recent["activities"] == 1


def test_heart_rate_reserve_zones_start_from_resting_heart_rate_at_whole_bpm(
    tmp_path, steady_run_fit
):
    client = client_with(tmp_path, ("run.fit", steady_run_fit), settings=False)
    client.put(
        "/api/settings",
        json=SETTINGS | {"zone_model": "hr_reserve_percent", "resting_heart_rate_bpm": 49},
    )
    activity = client.get("/api/activities").json()["items"][0]

    zones = client.get(f"/api/activities/{activity['id']}").json()["zones"]

    assert [(z["low_bpm"], z["high_bpm"], z["share"]) for z in zones] == [
        (None, 133, 0.0),
        (134, 147, 1.0),
        (148, 161, 0.0),
        (162, 175, 0.0),
        (176, None, 0.0),
    ]

import dataclasses
import datetime as dt
import math

import pytest
from makerundev import Activity, Sport
from makerundev.metrics import (
    CriticalSpeed,
    aerobic_decoupling,
    best_efforts,
    critical_speed,
    elevation_change,
    estimated_power,
    grade_adjusted_pace,
    splits,
    summarize,
    time_in_zones,
    training_load,
    trimp,
    vdot,
)

START = dt.datetime(2026, 3, 1, 7, 0, tzinfo=dt.UTC)


def run(rows):
    return Activity.from_rows(
        [{"timestamp": START + dt.timedelta(seconds=r.pop("t")), **r} for r in rows],
        sport=Sport.RUNNING,
    )


def steady(seconds, speed, start_t=0.0, start_d=0.0, **extra):
    return [
        {"t": start_t + i, "distance": start_d + i * speed, **extra} for i in range(seconds + 1)
    ]


def test_summary_counts_only_moving_time():
    rows = steady(600, 3.0)
    rows += [{"t": 600.0 + i, "distance": 1800.0} for i in range(1, 61)]
    rows += steady(300, 3.0, start_t=720.0, start_d=1800.0)[0:]

    summary = summarize(run(rows))

    assert summary.distance_m == 2700.0
    assert summary.elapsed_s == 1020.0
    assert summary.moving_s == 900.0
    assert summary.pace_s_per_km == pytest.approx(900 / 2.7)


def test_elevation_change_ignores_noise_below_threshold():
    altitudes = [100, 102, 99, 101, 100]
    altitudes += [*range(101, 111), 108, *range(111, 121), 119, 120]
    altitudes += [*range(119, 109, -1), 111]

    assert elevation_change(altitudes, threshold_m=3.0) == (20.0, 10.0)


def test_best_efforts_interpolate_and_skip_distances_longer_than_the_run():
    rows = steady(250, 4.0)
    rows += steady(200, 5.0, start_t=250.0, start_d=1000.0)[1:]
    rows += steady(125, 4.0, start_t=450.0, start_d=2000.0)[1:]

    efforts = best_efforts(run(rows), distances_m=(400.0, 1000.0, 1609.344, 5000.0))

    assert efforts == pytest.approx({400.0: 80.0, 1000.0: 200.0, 1609.344: 352.336})


def test_critical_speed_fits_efforts_of_two_to_twenty_minutes_by_least_squares():
    efforts = {500.0: 119.0, 600.0: 120.0, 2900.0: 660.0, 4920.0: 1200.0, 5100.0: 1201.0}

    fit = critical_speed(efforts)

    assert fit == CriticalSpeed(speed_mps=pytest.approx(4.0), d_prime_m=pytest.approx(500 / 3))


@pytest.mark.parametrize(
    "efforts",
    [
        {400.0: 70.0, 1000.0: 240.0, 10000.0: 2400.0},
        {1000.0: 200.0, 900.0: 400.0},
        {800.0: 200.0, 1800.0: 400.0},
        {1200.0: 300.0, 1300.0: 300.0},
    ],
    ids=["one-effort-in-window", "non-positive-speed", "non-positive-d-prime", "same-duration"],
)
def test_critical_speed_is_unavailable_without_a_meaningful_fit(efforts):
    assert critical_speed(efforts) is None


@pytest.mark.parametrize(
    ("distance_m", "time_s"),
    [(5000.0, 1197.0), (10000.0, 2481.0), (21097.5, 5495.0), (42195.0, 11449.0)],
    ids=["5k", "10k", "half-marathon", "marathon"],
)
def test_vdot_matches_the_vdot_50_row_of_daniels_tables(distance_m, time_s):
    assert vdot(distance_m, time_s) == pytest.approx(50.0, abs=0.05)


def test_vdot_follows_daniels_and_gilbert_for_efforts_of_three_minutes_to_five_hours():
    assert vdot(5000.0, 1200.0) == pytest.approx(49.806, abs=0.001)
    assert vdot(1000.0, 180.0) is not None
    assert vdot(42195.0, 18000.0) is not None


@pytest.mark.parametrize(
    ("distance_m", "time_s"),
    [
        (1000.0, 179.9),
        (42195.0, 18000.1),
        (-50000.0, 1200.0),
        (math.inf, 1200.0),
        (1000.0, 17000.0),
    ],
    ids=[
        "under-three-minutes",
        "over-five-hours",
        "negative-distance",
        "infinite-distance",
        "walking",
    ],
)
def test_vdot_is_unavailable_outside_its_model(distance_m, time_s):
    assert vdot(distance_m, time_s) is None


def test_splits_interpolate_boundaries_and_leave_pauses_out_of_moving_time():
    rows = steady(350, 3.0)
    rows += [{"t": 350.0 + i, "distance": 1050.0} for i in range(1, 50)]
    rows += steady(290, 5.0, start_t=400.0, start_d=1050.0)
    activity = run(rows)

    result = splits(activity)

    assert [s.distance_m for s in result] == pytest.approx([1000.0, 1000.0, 500.0])
    assert [s.elapsed_s for s in result] == pytest.approx([1000 / 3, 590 - 1000 / 3, 100.0])
    assert [s.moving_s for s in result] == pytest.approx([1000 / 3, 50 / 3 + 190, 100.0])
    assert [s.pace_s_per_km for s in result] == pytest.approx([1000 / 3, 50 / 3 + 190, 200.0])
    summary = summarize(activity)
    assert sum(s.elapsed_s for s in result) == pytest.approx(summary.elapsed_s)
    assert sum(s.moving_s for s in result) == pytest.approx(summary.moving_s)


def test_splits_give_one_partial_split_under_a_kilometre_and_none_without_distance():
    rows = steady(100, 3.0) + [{"t": 100.0 + i, "distance": 300.0} for i in range(1, 21)]
    short = splits(run(rows))
    assert len(short) == 1
    assert short[0].distance_m == pytest.approx(300.0)
    assert short[0].elapsed_s == pytest.approx(120.0)
    assert short[0].moving_s == pytest.approx(100.0)
    assert short[0].pace_s_per_km == pytest.approx(1000 / 3)

    assert splits(run([{"t": float(i), "distance": 0.0} for i in range(60)])) == []


def test_splits_end_on_an_exact_kilometre_and_have_no_pace_without_moving_time():
    rows = steady(300, 3.0)
    rows += steady(300, 3.0, start_t=500.0, start_d=2100.0)

    result = splits(run(rows))

    assert [s.distance_m for s in result] == pytest.approx([1000.0, 1000.0, 1000.0])
    assert [s.elapsed_s for s in result] == pytest.approx([950 / 3, 500 / 3, 950 / 3])
    assert [s.moving_s for s in result] == pytest.approx([300.0, 0.0, 300.0])
    assert [s.pace_s_per_km for s in result] == [pytest.approx(300.0), None, pytest.approx(300.0)]


def test_time_in_zones_splits_recorded_time_by_heart_rate():
    rows = steady(99, 3.0, heart_rate=120)
    rows += steady(200, 3.0, start_t=100.0, start_d=300.0, heart_rate=130)

    assert time_in_zones(run(rows), boundaries_bpm=(130, 160)) == [100.0, 200.0, 0.0]


def test_trimp_follows_banister_formula():
    rows = steady(3600, 3.0, heart_rate=125)

    expected = 60 * 0.5 * 0.64 * math.exp(1.92 * 0.5)
    assert trimp(run(rows), resting_hr=50, max_hr=200) == pytest.approx(expected)


def test_aerobic_decoupling_compares_efficiency_of_both_halves_of_a_run():
    rows = steady(1000, 3.0, heart_rate=140)
    rows += steady(1000, 3.0, start_t=1001.0, start_d=3003.0, heart_rate=147)

    activity = run(rows)

    assert aerobic_decoupling(activity) == pytest.approx((1 - 140 / 147) * 100, abs=0.01)
    assert aerobic_decoupling(dataclasses.replace(activity, sport=Sport.CYCLING)) is None


def test_training_load_fills_rest_days_and_reports_form_going_into_the_day():
    day0 = dt.date(2026, 3, 1)

    frame = training_load({day0: 100.0}, start=day0, end=day0 + dt.timedelta(days=1))

    assert frame["date"].to_list() == [day0, day0 + dt.timedelta(days=1)]
    assert frame["load"].to_list() == [100.0, 0.0]
    assert frame["fitness"].to_list() == pytest.approx([100 / 42, 100 / 42 * 41 / 42])
    assert frame["fatigue"].to_list() == pytest.approx([100 / 7, 100 / 7 * 6 / 7])
    assert frame["form"].to_list() == pytest.approx([0.0, 100 / 42 - 100 / 7])


@pytest.mark.parametrize(
    ("grade", "cost"),
    [(0.1, 5.968214), (-0.6, 4.0323054375)],
)
def test_grade_adjusted_pace_matches_hand_computed_constant_grades(grade, cost):
    rows = [{"t": i * 3, "distance": i * 10, "altitude": 200 + grade * i * 10} for i in range(101)]
    activity = run(rows)
    expected = 300 * 3.6 / cost
    assert grade_adjusted_pace(activity) == pytest.approx(expected)
    assert summarize(activity).grade_adjusted_pace_s_per_km == pytest.approx(expected)


def test_grade_adjusted_pace_window_is_distance_based_with_irregular_samples():
    distances = [0, 1, 10, 30, 100, 300, 600, 900, 1000]
    activity = run([{"t": d / 10, "distance": d, "altitude": 100 + d * 0.1} for d in distances])
    assert grade_adjusted_pace(activity) == pytest.approx(100 * 3.6 / 5.968214)


def test_grade_adjusted_pace_window_shifts_inside_the_run_at_its_ends():
    rows = [{"t": i * 3, "distance": i * 10, "altitude": 103 if i == 0 else 100} for i in range(21)]
    expected = 60 * 1000 / (30 * 2.7459239375 / 3.6 + 10 * 3.142100669921875 / 3.6 + 160)
    assert grade_adjusted_pace(run(rows)) == pytest.approx(expected)


def test_grade_adjusted_pace_does_not_smooth_across_a_pause():
    rows = [{"t": i * 3, "distance": i * 10, "altitude": 100 + i} for i in range(51)]
    rows += [{"t": 160, "distance": 500, "altitude": 1000}]
    rows += [
        {"t": 160 + i * 3, "distance": 500 + i * 10, "altitude": 1000 - i} for i in range(1, 51)
    ]
    expected = 300 * 1000 / (500 * 5.968214 / 3.6 + 500 * 2.151706 / 3.6)
    assert grade_adjusted_pace(run(rows)) == pytest.approx(expected)


def test_grade_adjusted_pace_excludes_recording_gaps_and_clamps_extreme_grades():
    rows = [
        {"t": 0, "distance": 0, "altitude": 0},
        {"t": 10, "distance": 100, "altitude": 100},
        {"t": 100, "distance": 10000, "altitude": -10000},
        {"t": 110, "distance": 10100, "altitude": -10000},
    ]
    expected = 20 * 1000 / (100 * 19.4260145625 / 3.6 + 100)
    assert grade_adjusted_pace(run(rows)) == pytest.approx(expected)


@pytest.mark.parametrize("altitudes", [(None, 101, 102), (100, 101, math.inf)])
def test_grade_adjusted_pace_is_unavailable_with_missing_or_invalid_elevation(altitudes):
    activity = run([{"t": i, "distance": i * 3, "altitude": a} for i, a in enumerate(altitudes)])
    assert grade_adjusted_pace(activity) is None


def test_grade_adjusted_pace_is_only_defined_for_moving_runs():
    assert grade_adjusted_pace(run([{"t": 0, "distance": 0, "altitude": 100}])) is None
    assert grade_adjusted_pace(run(steady(10, 0, altitude=100))) is None
    walking = Activity.from_rows(
        [
            {"timestamp": START, "distance": 0, "altitude": 100},
            {"timestamp": START + dt.timedelta(seconds=10), "distance": 30, "altitude": 103},
        ],
        sport=Sport.WALKING,
    )
    assert grade_adjusted_pace(walking) is None


@pytest.mark.parametrize(
    ("sport", "grade", "watts"),
    [
        (Sport.TREADMILL_RUNNING, 0.0, 228.67),
        (Sport.RUNNING, 0.1, 364.95),
        (Sport.RUNNING, -0.1, 156.20),
        (Sport.RUNNING, None, None),
    ],
)
def test_estimated_power_matches_hand_computed_constant_grades(sport, grade, watts):
    rows = [
        {"t": i * 3, "distance": i * 10, **({} if grade is None else {"altitude": grade * i * 10})}
        for i in range(101)
    ]
    power = estimated_power(dataclasses.replace(run(rows), sport=sport), body_mass_kg=70)
    assert power == (watts if watts is None else pytest.approx(watts, abs=0.01))


RUNNING_DYNAMICS = {
    "ground_contact_time": "avg_ground_contact_time",
    "vertical_oscillation": "avg_vertical_oscillation",
    "step_length": "avg_step_length",
}


@pytest.mark.parametrize("column", RUNNING_DYNAMICS)
def test_running_dynamics_averages_drop_zeros_and_weight_moving_intervals(column):
    rows = [
        {"t": 0.0, "distance": 0.0, column: 200.0, "cadence": 200.0},
        {"t": 1.0, "distance": 3.0, column: 0.0, "cadence": 0.0},
        {"t": 2.0, "distance": 6.0, column: 320.0, "cadence": 320.0},
        {"t": 4.0, "distance": 12.0, column: 260.0, "cadence": 260.0},
        {"t": 5.0, "distance": 12.0, column: 900.0, "cadence": 900.0},
        {"t": 6.0, "distance": 12.0, column: 700.0, "cadence": 700.0},
    ]

    summary = summarize(run(rows))

    assert getattr(summary, RUNNING_DYNAMICS[column]) == pytest.approx((200 + 320 * 2) / 3)
    assert summary.avg_cadence == pytest.approx((200 + 0 + 320 * 2) / 4)


def test_summary_tolerates_a_stream_stored_without_running_dynamics():
    rows = steady(600, 3.0, heart_rate=140.0)
    full = run(rows)
    stored = Activity(
        sport=full.sport,
        start_time=full.start_time,
        records=full.records.drop(list(RUNNING_DYNAMICS)),
    )

    summary = summarize(stored)

    assert summary.distance_m == 1800.0
    assert summary.avg_heart_rate == 140.0
    for attribute in RUNNING_DYNAMICS.values():
        assert getattr(summary, attribute) is None

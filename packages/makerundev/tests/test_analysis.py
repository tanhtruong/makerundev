import dataclasses
import datetime as dt
import math

import pytest
from makerundev import Activity, Sport
from makerundev.analysis import ZoneTime, analyse
from makerundev.metrics import BANISTER_FEMALE

START = dt.datetime(2026, 3, 1, 7, 0, tzinfo=dt.UTC)
RUNNER = {
    "body_mass_kg": 60.0,
    "max_hr": 200,
    "resting_hr": 50,
    "zone_boundaries_bpm": (145.0,),
}


def activity(rows, sport=Sport.RUNNING):
    return Activity.from_rows(
        [{"timestamp": START + dt.timedelta(seconds=r.pop("t")), **r} for r in rows],
        sport=sport,
    )


def two_halves(**extra):
    first = [
        {"t": i, "distance": i * 3.0, "altitude": 10.0, "heart_rate": 140, **extra}
        for i in range(1001)
    ]
    second = [
        {"t": 1001 + i, "distance": 3003.0 + i * 3.0, "altitude": 10.0, "heart_rate": 147, **extra}
        for i in range(1001)
    ]
    return first + second


def banister(minutes, heart_rate, factor=0.64, exponent=1.92):
    reserve = (heart_rate - 50) / 150
    return minutes * reserve * factor * math.exp(exponent * reserve)


def test_analysis_gives_every_number_for_a_run_with_heart_rate_and_runner_inputs():
    run = activity(two_halves())

    result = analyse(run, **RUNNER)

    assert (result.summary.distance_m, result.summary.moving_s) == (6003.0, 2001.0)
    assert result.summary.avg_heart_rate == pytest.approx((140 * 1001 + 147 * 1000) / 2001)
    assert result.aerobic_decoupling_percent == pytest.approx((1 - 140 / 147) * 100, abs=0.01)
    assert result.estimated_power_w == pytest.approx(0.98 * 60 * 3 + 1.205 * 0.24 / 2 * 27)
    assert result.zones == (
        ZoneTime(number=1, seconds=1001.0, share=pytest.approx(1001 / 2001)),
        ZoneTime(number=2, seconds=1000.0, share=pytest.approx(1000 / 2001)),
    )
    assert result.trimp == pytest.approx(banister(1001 / 60, 140) + banister(1000 / 60, 147))


def test_analysis_uses_the_trimp_coefficients_given():
    result = analyse(activity(two_halves()), **RUNNER, trimp_coefficients=BANISTER_FEMALE)

    factor, exponent = BANISTER_FEMALE
    assert result.trimp == pytest.approx(
        banister(1001 / 60, 140, factor, exponent) + banister(1000 / 60, 147, factor, exponent)
    )


def without(*names):
    return {key: value for key, value in RUNNER.items() if key not in names}


def gapped_heart_rate():
    rows = [
        {"t": i * 40, "distance": i * 120.0, "altitude": 10.0, "heart_rate": 150} for i in range(4)
    ]
    rows += [{"t": 160 + i, "distance": 480.0 + i * 3.0, "altitude": 10.0} for i in range(101)]
    return activity(rows)


@pytest.mark.parametrize(
    ("run", "inputs", "absent", "present"),
    [
        pytest.param(
            activity(two_halves()),
            without("body_mass_kg"),
            {"estimated_power_w"},
            {"aerobic_decoupling_percent", "zones", "trimp"},
            id="no body mass",
        ),
        pytest.param(
            activity(two_halves()),
            without("resting_hr"),
            {"trimp"},
            {"zones", "estimated_power_w"},
            id="no resting heart rate",
        ),
        pytest.param(
            activity(two_halves()),
            without("max_hr"),
            {"trimp"},
            {"zones"},
            id="no max heart rate",
        ),
        pytest.param(
            activity(two_halves()),
            without("zone_boundaries_bpm"),
            {"zones"},
            {"trimp"},
            id="no zone boundaries",
        ),
        pytest.param(
            activity([{k: v for k, v in r.items() if k != "heart_rate"} for r in two_halves()]),
            RUNNER,
            {"aerobic_decoupling_percent", "zones", "trimp"},
            {"estimated_power_w"},
            id="no heart rate in the stream",
        ),
        pytest.param(
            gapped_heart_rate(),
            RUNNER,
            {"zones", "trimp"},
            {"estimated_power_w"},
            id="heart rate only across recording gaps",
        ),
        pytest.param(
            activity(two_halves(), sport=Sport.CYCLING),
            RUNNER,
            {"aerobic_decoupling_percent", "estimated_power_w"},
            {"zones", "trimp"},
            id="not a run",
        ),
    ],
)
def test_a_number_is_absent_exactly_when_its_input_or_data_is_missing(run, inputs, absent, present):
    result = dataclasses.asdict(analyse(run, **inputs))

    assert {name for name in absent | present if result[name] is None} == absent

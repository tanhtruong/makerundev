import datetime as dt
from collections.abc import Callable

import polars as pl
import pytest
from makerundev_server import charts


def positions(lat: list[float | None], lon: list[float | None]) -> pl.DataFrame:
    return pl.DataFrame(
        {"latitude": lat, "longitude": lon},
        schema={"latitude": pl.Float64, "longitude": pl.Float64},
    )


def test_route_shape_puts_north_up_and_east_right():
    shape = charts.route_shape([(55.0, 12.0), (55.01, 12.01)])

    assert shape.points == [(0.0, pytest.approx(1000.0)), (pytest.approx(573.50, abs=0.01), 0.0)]


def test_route_shape_keeps_the_aspect_ratio_of_the_ground():
    shape = charts.route_shape([(60.0, 10.0), (60.01, 10.01)])

    assert shape.height == pytest.approx(1000.0)
    assert shape.width == pytest.approx(499.92, abs=0.01)


def test_route_points_drop_rows_without_a_position():
    sampled = charts.route_points(
        positions([55.0, None, 55.01, 55.02], [12.0, 12.005, None, 12.01])
    )
    assert sampled == [(55.0, 12.0), (55.02, 12.01)]


@pytest.mark.parametrize(
    ("lat", "lon"),
    [([], []), ([None, None], [None, None]), ([55.0, None], [12.0, None])],
)
def test_route_is_none_without_two_positions(lat, lon):
    assert charts.route_points(positions(lat, lon)) is None


@pytest.mark.parametrize("count", [1200, 6000])
def test_route_points_are_at_most_600_and_keep_both_ends(count):
    lat = [55.0 + i * 1e-5 for i in range(count)]
    lon = [12.0 + i * 1e-5 for i in range(count)]

    sampled = charts.route_points(positions(lat, lon))

    assert sampled is not None
    assert 300 < len(sampled) <= 600
    assert sampled[0] == (lat[0], lon[0])
    assert sampled[-1] == (lat[-1], lon[-1])


START = dt.datetime(2026, 3, 1, 7, tzinfo=dt.UTC)


def stream(
    count: int,
    heart_rate: Callable[[int], float | None] = lambda i: 140.0,
    speed: Callable[[int], float] = lambda i: 4.0,
    distance: Callable[[int], float] = lambda i: i * 4.0,
) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [START + dt.timedelta(seconds=i) for i in range(count)],
            "distance": [distance(i) for i in range(count)],
            "speed": [speed(i) for i in range(count)],
            "heart_rate": [heart_rate(i) for i in range(count)],
            "altitude": [None] * count,
        },
        schema={
            "timestamp": pl.Datetime("us", "UTC"),
            "distance": pl.Float64,
            "speed": pl.Float64,
            "heart_rate": pl.Float64,
            "altitude": pl.Float64,
        },
    )


def test_a_short_activity_returns_every_sample_even_where_it_stood_still():
    rows = charts.chart_series(
        stream(1000, heart_rate=lambda i: 100.0 + i % 7, distance=lambda i: max(0, i - 300) * 4.0)
    )

    assert len(rows) == 1000
    assert [row.heart_rate_bpm for row in rows[:7]] == [
        100.0,
        101.0,
        102.0,
        103.0,
        104.0,
        105.0,
        106.0,
    ]
    assert rows[999] == charts.SeriesRow(
        distance_m=2796.0,
        elapsed_s=999.0,
        pace_s_per_km=250.0,
        heart_rate_bpm=100.0 + 999 % 7,
        altitude_m=None,
    )


def test_thinning_keeps_a_one_sample_spike_and_dip():
    rows = charts.chart_series(
        stream(5000, heart_rate=lambda i: {1234: 200.0, 3210: 90.0}.get(i, 140.0))
    )

    assert len(rows) <= 1000
    heart_rates = [row.heart_rate_bpm for row in rows]
    assert (max(heart_rates), min(heart_rates)) == (200.0, 90.0)


def test_each_bucket_keeps_the_order_of_its_extremes_at_its_first_and_last_sample():
    rows = charts.chart_series(
        stream(5000, heart_rate=lambda i: {3: 170.0, 6: 120.0}.get(i, 140.0))
    )

    first, second = rows[0], rows[1]
    assert (first.distance_m, first.elapsed_s, first.heart_rate_bpm) == (0.0, 0.0, 170.0)
    assert (second.distance_m, second.elapsed_s, second.heart_rate_bpm) == (36.0, 9.0, 120.0)


def test_a_stretch_without_heart_rate_is_null_while_pace_goes_on():
    def heart_rate(i: int) -> float | None:
        if i == 2001:
            return 175.0
        return None if 2003 <= i < 3000 else 140.0

    rows = charts.chart_series(stream(5000, heart_rate=heart_rate))

    assert 175.0 in [row.heart_rate_bpm for row in rows if row.distance_m < 8100.0]
    gap = [row for row in rows if 8100.0 <= row.distance_m <= 11900.0]
    assert gap
    assert {row.heart_rate_bpm for row in gap} == {None}
    assert {row.pace_s_per_km for row in gap} == {250.0}


def test_an_activity_without_distance_has_no_series():
    records = stream(50).with_columns(distance=pl.lit(None, pl.Float64))

    assert charts.chart_series(records) == []


def test_pace_bounds_ignore_a_walk_break_and_other_bounds_are_the_true_range():
    records = stream(
        1000,
        heart_rate=lambda i: 120.0 + i % 50,
        speed=lambda i: 0.6 if i < 10 else 4.0,
    )

    bounds = charts.series_bounds(records)

    assert bounds.pace_s_per_km == charts.Bounds(low=250.0, high=250.0)
    assert bounds.heart_rate_bpm == charts.Bounds(low=120.0, high=169.0)
    assert bounds.altitude_m is None

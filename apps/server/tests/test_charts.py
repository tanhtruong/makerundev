import polars as pl
import pytest
from makerundev_server import charts


def positions(lat: list[float | None], lon: list[float | None]) -> pl.DataFrame:
    return pl.DataFrame(
        {"latitude": lat, "longitude": lon},
        schema={"latitude": pl.Float64, "longitude": pl.Float64},
    )


def points(route: charts.Route) -> list[tuple[float, float]]:
    pairs = (point.split(",") for point in route.points.split())
    return [(float(x), float(y)) for x, y in pairs]


def test_route_puts_north_up_and_east_right():
    route = charts.route(positions([55.0, 55.01], [12.0, 12.01]))
    assert route is not None
    (x_start, y_start), (x_end, y_end) = points(route)
    assert y_end < y_start
    assert x_end > x_start


def test_route_keeps_the_aspect_ratio_of_the_ground():
    route = charts.route(positions([60.0, 60.01], [10.0, 10.01]))
    assert route is not None
    inner_width = route.width - 2 * charts.INSET
    inner_height = route.height - 2 * charts.INSET
    assert inner_height == pytest.approx(charts.ROUTE_SIZE)
    assert inner_width / inner_height == pytest.approx(0.5, abs=0.001)


def test_route_drops_rows_without_a_position():
    route = charts.route(positions([55.0, None, 55.01, 55.02], [12.0, 12.005, None, 12.01]))
    assert route is not None
    assert len(points(route)) == 2


@pytest.mark.parametrize(
    ("lat", "lon"),
    [([], []), ([None, None], [None, None]), ([55.0, None], [12.0, None])],
)
def test_route_is_none_without_two_positions(lat, lon):
    assert charts.route(positions(lat, lon)) is None


def test_route_is_downsampled():
    count = 10 * charts.MAX_POINTS
    route = charts.route(
        positions([55.0 + i * 1e-5 for i in range(count)], [12.0 + i * 1e-5 for i in range(count)])
    )
    assert route is not None
    assert len(points(route)) == charts.MAX_POINTS + 1


def test_downsampled_route_ends_at_the_final_position():
    count = 10 * charts.MAX_POINTS + 7
    route = charts.route(
        positions([55.0 + i * 1e-5 for i in range(count)], [12.0 + i * 1e-5 for i in range(count)])
    )
    assert route is not None
    assert len(points(route)) == charts.MAX_POINTS + 2
    assert points(route)[-1] == pytest.approx((route.width - charts.INSET, charts.INSET), abs=0.1)

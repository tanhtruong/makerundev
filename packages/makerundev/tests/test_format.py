import pytest
from makerundev import format


@pytest.mark.parametrize(
    ("meters", "name"),
    [
        (11265.408, "7 miles"),
        (5000.0, "5 km"),
        (21097.5, "Half marathon"),
    ],
)
def test_distance_name_names_a_distance_in_the_unit_it_is_round_in(meters, name):
    assert format.distance_name(meters) == name

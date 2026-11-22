import datetime as dt

import pytest
from makerundev import ActivityFileError, Sport, load
from makerundev.io.strava import read_strava
from makerundev.model import STREAM_SCHEMA, Lap

START = dt.datetime(2026, 3, 1, 7, 0, tzinfo=dt.UTC)


def summary(**fields):
    return {
        "id": 9001,
        "name": "Morning Run",
        "sport_type": "Run",
        "trainer": False,
        "start_date": "2026-03-01T07:00:00Z",
    } | fields


def streams(seconds=3, **overrides):
    data = {
        "time": list(range(seconds)),
        "latlng": [[55.67 + i * 0.00003, 12.56] for i in range(seconds)],
        "distance": [i * 3.0 for i in range(seconds)],
        "altitude": [10.0] * seconds,
        "velocity_smooth": [3.0] * seconds,
        "heartrate": [140] * seconds,
        "cadence": [85] * seconds,
        "watts": [250] * seconds,
        "temp": [12] * seconds,
    } | overrides
    return {
        key: {
            "data": values,
            "series_type": "distance",
            "original_size": len(values),
            "resolution": "high",
        }
        for key, values in data.items()
        if values is not None
    }


def test_streams_are_mapped_onto_the_record_stream_in_canonical_units():
    activity = read_strava(summary(), streams())

    assert activity.source_format == "strava"
    assert activity.name == "Morning Run"
    assert activity.sport is Sport.RUNNING
    assert activity.start_time == START
    assert activity.device is None
    assert activity.records.schema == STREAM_SCHEMA
    assert activity.records.row(1, named=True) == {
        "timestamp": START + dt.timedelta(seconds=1),
        "latitude": pytest.approx(55.67003),
        "longitude": 12.56,
        "distance": 3.0,
        "speed": 3.0,
        "altitude": 10.0,
        "heart_rate": 140.0,
        "cadence": 170.0,
        "power": 250.0,
        "temperature": 12.0,
        "ground_contact_time": None,
        "vertical_oscillation": None,
        "step_length": None,
    }


def test_the_same_run_from_strava_and_from_its_fit_file_has_the_same_cadence(make_fit):
    fit = load(make_fit([{"t": float(i), "distance": i * 3.0, "cadence": 85} for i in range(3)]))

    strava = read_strava(summary(), streams())

    assert strava.records["cadence"].to_list() == fit.records["cadence"].to_list() == [170.0] * 3


def test_cadence_is_not_doubled_off_the_run():
    activity = read_strava(summary(sport_type="Ride"), streams())

    assert activity.records["cadence"].to_list() == [85.0] * 3


@pytest.mark.parametrize(
    ("fields", "overrides", "sport"),
    [
        ({"sport_type": "Run"}, {}, Sport.RUNNING),
        ({"sport_type": "Run", "trainer": True}, {}, Sport.TREADMILL_RUNNING),
        ({"sport_type": "Run"}, {"latlng": None}, Sport.TREADMILL_RUNNING),
        ({"sport_type": "TrailRun"}, {}, Sport.TRAIL_RUNNING),
        ({"sport_type": "TrailRun"}, {"latlng": None}, Sport.TRAIL_RUNNING),
        ({"sport_type": "VirtualRun"}, {}, Sport.TREADMILL_RUNNING),
        ({"sport_type": "Walk"}, {}, Sport.WALKING),
        ({"sport_type": "Hike"}, {}, Sport.HIKING),
        ({"sport_type": "Ride"}, {}, Sport.CYCLING),
        ({"sport_type": "GravelRide"}, {}, Sport.CYCLING),
        ({"sport_type": "EBikeRide"}, {}, Sport.CYCLING),
        ({"sport_type": "Swim"}, {}, Sport.SWIMMING),
        ({"sport_type": "Yoga"}, {}, Sport.OTHER),
        ({"sport_type": None, "type": "Run"}, {}, Sport.RUNNING),
    ],
)
def test_strava_sport_types_map_onto_sports(fields, overrides, sport):
    assert read_strava(summary(**fields), streams(**overrides)).sport is sport


def test_missing_streams_become_nulls_and_distance_falls_back_to_positions():
    only = streams(
        distance=None,
        altitude=None,
        velocity_smooth=None,
        heartrate=None,
        cadence=None,
        watts=None,
        temp=None,
    )

    records = read_strava(summary(), only).records

    for column in (
        "altitude",
        "heart_rate",
        "cadence",
        "power",
        "temperature",
        "ground_contact_time",
        "vertical_oscillation",
        "step_length",
    ):
        assert records[column].null_count() == records.height
    assert records["distance"][0] == 0.0
    assert records["distance"][2] == pytest.approx(6.67, abs=0.05)


def test_a_shorter_stream_is_padded_with_nulls():
    records = read_strava(summary(), streams(heartrate=[140, 141])).records

    assert records["heart_rate"].to_list() == [140.0, 141.0, None]


def test_streams_listed_by_type_are_read_like_keyed_ones():
    keyed = streams()
    listed = [{"type": key} | stream for key, stream in keyed.items()]

    assert read_strava(summary(), listed).records.equals(read_strava(summary(), keyed).records)


@pytest.mark.parametrize("without_time", [{}, streams(time=None), streams(time=[])])
def test_an_activity_without_a_time_stream_is_rejected(without_time):
    with pytest.raises(ActivityFileError, match="no time stream"):
        read_strava(summary(), without_time)


def test_an_unreadable_start_date_is_rejected():
    with pytest.raises(ActivityFileError, match="start_date"):
        read_strava(summary(start_date=None), streams())


def test_laps_of_a_detailed_activity_become_laps_in_order():
    laps = [
        {"start_date": "2026-03-01T07:00:00Z", "elapsed_time": 300, "distance": 1000.0},
        {"start_date": "2026-03-01T09:05:00+02:00", "elapsed_time": 290.5},
        {"start_date": None, "elapsed_time": 10, "distance": 30.0},
        None,
        {"start_date": "2026-03-01T07:10:00Z", "elapsed_time": True, "distance": "5"},
    ]

    activity = read_strava(summary(laps=laps), streams())

    assert activity.laps == (
        Lap(start_time=START, elapsed_s=300.0, distance_m=1000.0),
        Lap(start_time=START + dt.timedelta(minutes=5), elapsed_s=290.5, distance_m=None),
        Lap(start_time=START + dt.timedelta(minutes=10), elapsed_s=None, distance_m=None),
    )
    assert [lap.start_time.tzinfo for lap in activity.laps] == [dt.UTC] * 3
    assert read_strava(summary(laps=3), streams()).laps == ()

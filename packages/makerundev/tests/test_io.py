import datetime as dt
import gzip
from pathlib import Path

import pytest
from fit_tool.profile.profile_type import Sport as FitSport
from fit_tool.profile.profile_type import SubSport
from makerundev import ActivityFileError, Lap, Sport, load

FIXTURES = Path(__file__).parent / "fixtures"
START = dt.datetime(2026, 3, 1, 7, 0, tzinfo=dt.UTC)


def test_fit_file_is_normalised_to_canonical_units(make_fit, tmp_path):
    rows = [
        {
            "t": 0.0,
            "lat": 55.67,
            "lon": 12.56,
            "distance": 0.0,
            "speed": 3.0,
            "altitude": 10.5,
            "hr": 140,
            "cadence": 85,
            "power": 250,
        },
        {
            "t": 1.0,
            "lat": 55.67003,
            "lon": 12.56,
            "distance": 3.0,
            "speed": 3.0,
            "altitude": 10.5,
            "hr": 141,
            "cadence": 86,
            "power": 251,
        },
    ]
    data = make_fit(rows, sport=FitSport.RUNNING, sub_sport=SubSport.TRAIL)

    activity = load(data)

    assert activity.source_format == "fit"
    assert activity.sport is Sport.TRAIL_RUNNING
    assert activity.start_time == START
    assert activity.device == "garmin fr965"
    first = activity.records.row(0, named=True)
    assert first["timestamp"] == START
    assert first["latitude"] == pytest.approx(55.67, abs=1e-6)
    assert first["longitude"] == pytest.approx(12.56, abs=1e-6)
    assert first["heart_rate"] == 140
    assert first["cadence"] == 170
    assert first["power"] == 250
    assert first["speed"] == pytest.approx(3.0)
    assert activity.records["distance"].to_list() == [0.0, 3.0]

    gz = tmp_path / "run.fit.gz"
    gz.write_bytes(gzip.compress(data))
    assert load(gz).records.equals(activity.records)


def test_fit_laps_are_sorted_and_those_without_a_start_are_dropped(make_fit):
    rows = [{"t": float(i), "distance": i * 3.0} for i in range(3)]
    laps = [
        {"t": 1.0, "elapsed": 0.5},
        {"t": 0.0, "elapsed": 1.0, "distance": 3.0},
        {"elapsed": 1.0, "distance": 6.0},
    ]

    activity = load(make_fit(rows, laps=laps))

    assert activity.laps == (
        Lap(start_time=START, elapsed_s=1.0, distance_m=3.0),
        Lap(start_time=START + dt.timedelta(seconds=1), elapsed_s=0.5, distance_m=None),
    )


def test_gpx_track_gets_distance_and_speed_from_positions():
    activity = load(FIXTURES / "run.gpx")

    assert activity.source_format == "gpx"
    assert activity.laps == ()
    assert activity.sport is Sport.RUNNING
    assert activity.start_time == START
    assert activity.records["heart_rate"].to_list() == [130, 135, 140]
    assert activity.records["cadence"].to_list() == [168, 170, 172]
    assert activity.records["distance"].to_list() == pytest.approx([0.0, 111.19, 222.39], abs=0.05)
    assert activity.records["speed"][1] == pytest.approx(111.19 / 30, abs=0.01)


def test_tcx_trackpoints_are_read_with_extensions():
    activity = load(FIXTURES / "run.tcx")

    assert activity.source_format == "tcx"
    assert activity.sport is Sport.RUNNING
    assert activity.start_time == START
    assert activity.records["distance"].to_list() == [0.0, 95.0, 190.0]
    assert activity.records["heart_rate"].to_list() == [128, 133, 138]
    assert activity.records["cadence"].to_list() == [166, 168, 170]
    assert activity.records["speed"].to_list() == [3.1, 3.2, 3.3]
    assert activity.records["altitude"].to_list() == [12.0, 12.4, 12.8]
    assert activity.laps == (Lap(start_time=START, elapsed_s=60.0, distance_m=190.0),)


def test_tcx_laps_are_read_in_utc_and_those_without_a_start_are_dropped():
    point = "<Track><Trackpoint><Time>2026-03-01T07:00:00Z</Time></Trackpoint></Track>"
    tcx = f"""<?xml version="1.0"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities><Activity Sport="Running">
    <Lap StartTime="2026-03-01T08:05:00+01:00"><DistanceMeters>1000.0</DistanceMeters>{point}</Lap>
    <Lap><TotalTimeSeconds>60.0</TotalTimeSeconds>{point}</Lap>
  </Activity></Activities>
</TrainingCenterDatabase>"""

    activity = load(tcx.encode())

    assert activity.laps == (
        Lap(start_time=START + dt.timedelta(minutes=5), elapsed_s=None, distance_m=1000.0),
    )


def test_unreadable_input_raises_activity_file_error(steady_run_fit):
    with pytest.raises(ActivityFileError):
        load(b"definitely not an activity file")
    with pytest.raises(ActivityFileError):
        load(steady_run_fit[: len(steady_run_fit) // 2])
    with pytest.raises(ActivityFileError):
        load(b"<?xml version='1.0'?><gpx><trk><trkseg></trkseg></trk></gpx>")

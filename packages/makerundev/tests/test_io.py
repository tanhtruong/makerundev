import datetime as dt
import gzip
import zipfile
from pathlib import Path

import makerundev.io
import pytest
from fit_tool.profile.profile_type import Sport as FitSport
from fit_tool.profile.profile_type import SubSport
from makerundev import ActivityFileError, Lap, Sport, load
from makerundev.io import unzip

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


def test_fit_running_dynamics_are_read_in_canonical_units(make_fit):
    rows = [
        {
            "t": 0.0,
            "distance": 0.0,
            "stance_time": 250.0,
            "vertical_oscillation": 85.0,
            "step_length": 1100.0,
        },
        {
            "t": 1.0,
            "distance": 3.0,
            "stance_time": 0.0,
            "vertical_oscillation": 0.0,
            "step_length": 0.0,
        },
        {"t": 2.0, "distance": 6.0},
    ]

    records = load(make_fit(rows, sport=FitSport.HIKING)).records

    assert records["ground_contact_time"].to_list() == [250.0, 0.0, None]
    assert records["vertical_oscillation"].to_list() == [85.0, 0.0, None]
    assert records["step_length"].to_list() == pytest.approx([1.1, 0.0, None])


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
    assert activity.name == "Morning Run"
    assert activity.laps == ()
    assert activity.sport is Sport.RUNNING
    assert activity.start_time == START
    assert activity.records["heart_rate"].to_list() == [130, 135, 140]
    assert activity.records["cadence"].to_list() == [168, 170, 172]
    assert activity.records["distance"].to_list() == pytest.approx([0.0, 111.19, 222.39], abs=0.05)
    assert activity.records["speed"][1] == pytest.approx(111.19 / 30, abs=0.01)


@pytest.mark.parametrize(
    ("header", "first_track", "name"),
    [
        ("<metadata><name>Exported</name></metadata>", "<name>Harbour loop</name>", "Harbour loop"),
        ("<metadata><name>Exported</name></metadata>", "<name> </name>", "Exported"),
        ("", "", None),
    ],
)
def test_gpx_name_falls_back_from_the_first_track_to_the_metadata(header, first_track, name):
    point = '<trkpt lat="55.67" lon="12.56"><time>2026-03-01T07:00:00Z</time></trkpt>'
    gpx = (
        f'<gpx xmlns="http://www.topografix.com/GPX/1/1">{header}'
        f"<trk>{first_track}<trkseg>{point}</trkseg></trk>"
        f"<trk><name>Second track</name><trkseg>{point}</trkseg></trk></gpx>"
    )

    assert load(gpx.encode()).name == name


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
    assert activity.laps[0].start_time.utcoffset() == dt.timedelta(0)


def test_unreadable_input_raises_activity_file_error(steady_run_fit):
    with pytest.raises(ActivityFileError):
        load(b"definitely not an activity file")
    with pytest.raises(ActivityFileError):
        load(steady_run_fit[: len(steady_run_fit) // 2])
    with pytest.raises(ActivityFileError):
        load(b"<?xml version='1.0'?><gpx><trk><trkseg></trkseg></trk></gpx>")


def test_single_activity_zip_is_read_as_the_file_inside(steady_run_fit, make_zip, tmp_path):
    data = make_zip(
        ("export/", b""),
        ("export/readme.txt", b"Exported from Garmin Connect"),
        ("export\\123_ACTIVITY.fit", steady_run_fit),
    )

    assert unzip(data) == ("123_ACTIVITY.fit", steady_run_fit)
    path = tmp_path / "123.zip"
    path.write_bytes(data)
    assert load(path).records.equals(load(steady_run_fit).records)


def test_zip_entry_is_recognised_by_its_root_element_not_its_name(make_zip):
    gpx = (FIXTURES / "run.gpx").read_bytes()
    tcx = (FIXTURES / "run.tcx").read_bytes()
    declaration, body = gpx.split(b"?>", 1)
    commented = declaration + b"?><!--" + b" " * 10_000 + b"-->" + body

    assert unzip(make_zip(("notes.xml", b"<notes>about <gpx> files</notes>"), ("track", gpx))) == (
        "track",
        gpx,
    )
    assert unzip(make_zip(("commented.gpx", commented))) == ("commented.gpx", commented)
    assert load(make_zip(("lap.data", tcx))).source_format == "tcx"


def test_zip_must_hold_exactly_one_activity_file(steady_run_fit, make_zip):
    with pytest.raises(ActivityFileError, match="no FIT, GPX or TCX"):
        load(make_zip(("readme.txt", b"nothing here")))
    with pytest.raises(ActivityFileError, match="more than one activity file"):
        load(make_zip(("a.fit", steady_run_fit), ("b.fit", steady_run_fit)))


def test_zip_may_hold_16_files_besides_its_directories(steady_run_fit, make_zip):
    folders = [(f"{i}/", b"") for i in range(4)]
    filler = [(f"{i}.txt", b"") for i in range(15)]

    assert unzip(make_zip(*folders, ("run.fit", steady_run_fit), *filler)) is not None
    with pytest.raises(ActivityFileError, match="more than 16 files"):
        unzip(make_zip(("run.fit", steady_run_fit), *filler, ("extra.txt", b"")))


def test_zip_directory_is_bounded_before_it_is_parsed(steady_run_fit, make_zip):
    flood = [(f"{i:08}.txt", b"") for i in range(1200)]
    with pytest.raises(ActivityFileError, match="directory is larger than 64 KB"):
        unzip(make_zip(("run.fit", steady_run_fit), *flood))


def test_zip64_archive_is_refused(steady_run_fit, make_zip):
    data = make_zip(("run.fit", steady_run_fit))
    end = data.rindex(b"PK\x05\x06")
    locator = b"PK\x06\x07" + bytes(16)
    with pytest.raises(ActivityFileError, match="ZIP64"):
        unzip(data[:end] + locator + data[end:])


def test_zip_with_an_encrypted_entry_is_refused(steady_run_fit, make_zip):
    with pytest.raises(ActivityFileError, match="encrypted"):
        unzip(flag_first_entry_encrypted(make_zip(("run.fit", steady_run_fit))))


def flag_first_entry_encrypted(archive: bytes) -> bytes:
    data = bytearray(archive)
    data[data.index(b"PK\x03\x04") + 6] |= 0x1
    data[data.index(b"PK\x01\x02") + 8] |= 0x1
    return bytes(data)


@pytest.mark.parametrize("method", [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA])
def test_zip_entry_compressed_other_than_deflate_is_refused(steady_run_fit, make_zip, method):
    with pytest.raises(ActivityFileError, match="compression method"):
        unzip(make_zip(("run.fit", steady_run_fit), method=method))


def test_decompressed_size_cap_is_named_in_the_error(steady_run_fit, make_zip, monkeypatch):
    monkeypatch.setattr(makerundev.io, "MAX_DECOMPRESSED_BYTES", 1024 * 1024)
    padding = bytes(1024 * 1024)

    with pytest.raises(ActivityFileError, match="larger than 1 MB"):
        unzip(make_zip(("run.fit", steady_run_fit), ("padding.bin", padding)))
    with pytest.raises(ActivityFileError, match="larger than 1 MB"):
        load(gzip.compress(steady_run_fit + padding))


def test_damaged_zip_raises_activity_file_error(steady_run_fit, make_zip):
    data = make_zip(("run.fit", steady_run_fit))
    central = data.index(b"PK\x01\x02")
    end = data.rindex(b"PK\x05\x06")

    undecodable_name = bytearray(data)
    undecodable_name[central + 9] |= 0x08
    undecodable_name[central + 46 : central + 53] = b"\xff" * 7
    lying_offset = bytearray(data)
    lying_offset[end + 16 : end + 20] = (len(data) * 2).to_bytes(4, "little")
    future_version = bytearray(data)
    future_version[central + 6] = 99
    bad_signature = bytearray(data)
    bad_signature[central + 3] = 0

    for damaged in (
        data[: len(data) // 2],
        bytes(undecodable_name),
        bytes(lying_offset),
        bytes(future_version),
        bytes(bad_signature),
    ):
        with pytest.raises(ActivityFileError):
            unzip(damaged)

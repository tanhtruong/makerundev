import datetime as dt
import io
import math
import random
import re
import struct
from collections.abc import Sequence
from typing import Any
from xml.etree.ElementTree import Element

import fitdecode
import pytest
from defusedxml import ElementTree
from fit_tool.base_type import BaseType
from fit_tool.data_message import DataMessage
from fit_tool.developer_field import DeveloperField
from fit_tool.endian import Endian
from fit_tool.field import Field
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.developer_data_id_message import DeveloperDataIdMessage
from fit_tool.profile.messages.field_description_message import FieldDescriptionMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.messages.user_profile_message import UserProfileMessage
from fit_tool.profile.profile_type import FileType, Sport
from fitdecode.utils import compute_crc
from makerundev import ActivityFileError, load
from makerundev.io import Identifying, anonymize

START_LAT = 55.6761234
START_LON = 12.5683371
POINTS = 50
EARTH_RADIUS_KM = 6371.0088
FIT_START_MS = round(dt.datetime(2026, 3, 1, 7, tzinfo=dt.UTC).timestamp() * 1000)
FIT_POSITIONS = POINTS + 3
FIT_BOX_CORNERS = 2
FIT_RECORD, FIT_SINT16, FIT_SINT32, FIT_UINT32 = 20, 0x83, 0x85, 0x86
FIT_HOME = (664_190_000, 149_950_000)


def _coordinates(index: int, start_lat: float = START_LAT) -> tuple[str, str]:
    decimals = 4 if index % 5 == 0 else 7
    lat, lon = start_lat + index * 0.0001, START_LON + index * 0.00015
    return f"{lat:.{decimals}f}", f"{lon:.{decimals}f}"


def _gpx() -> bytes:
    points = []
    for index in range(POINTS):
        lat, lon = _coordinates(index)
        position = f"lat='{lat}'  lon = \"{lon}\"" if index % 2 else f'lat="{lat}" lon="{lon}"'
        points.append(
            f"<trkpt {position}><ele>12.{index % 10}</ele>"
            f"<time>2026-03-01T07:{index // 6:02d}:{index % 6 * 10:02d}Z</time>"
            f"<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>{120 + index}</gpxtpx:hr>"
            f"</gpxtpx:TrackPointExtension>"
            + (f'<x:fix lat="{lat}" lon="{lon}"/>' if index == 7 else "")
            + "</extensions></trkpt>"
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- recorded at lat="55" lon="12" -->
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
     xmlns:x="urn:example:fix">
  <metadata><name>Run from home</name>
    <bounds minlat="55.6761234" minlon="12.5683371" maxlat="55.6810234" maxlon="12.5756871"/>
  </metadata>
  <wpt lat="55.6760000" lon="12.5680000"><name>Home</name></wpt>
  <trk><type>running</type><trkseg>
{chr(10).join(points)}
  </trkseg></trk>
</gpx>
""".encode()


def _tcx(start_lat: float = START_LAT) -> bytes:
    points = []
    for index in range(POINTS):
        lat, lon = _coordinates(index, start_lat)
        space = " " if index % 2 else ""
        points.append(
            f"<t:Trackpoint><t:Time>2026-03-01T07:{index // 6:02d}:{index % 6 * 10:02d}Z</t:Time>"
            f"<t:Position><t:LatitudeDegrees>{space}{lat}{space}</t:LatitudeDegrees>"
            f"<t:LongitudeDegrees>{lon}</t:LongitudeDegrees></t:Position>"
            f"<t:AltitudeMeters>12.{index % 10}</t:AltitudeMeters>"
            f"<t:HeartRateBpm><t:Value>{120 + index}</t:Value></t:HeartRateBpm></t:Trackpoint>"
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<t:TrainingCenterDatabase xmlns:t="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <!-- recorded at <t:LatitudeDegrees>55</t:LatitudeDegrees> -->
  <t:Activities><t:Activity Sport="Running"><t:Id>2026-03-01T07:00:00Z</t:Id>
    <t:Lap StartTime="2026-03-01T07:00:00Z"><t:Track>
{chr(10).join(points)}
    </t:Track></t:Lap>
    <t:Creator><t:Name>Forerunner 965</t:Name><t:UnitId>3412345678</t:UnitId></t:Creator>
  </t:Activity></t:Activities>
  <t:Courses><t:Course><t:CoursePoint><t:Position>
    <t:LatitudeDegrees>55.6760000</t:LatitudeDegrees>
    <t:LongitudeDegrees>12.5680000</t:LongitudeDegrees>
  </t:Position></t:CoursePoint></t:Course></t:Courses>
</t:TrainingCenterDatabase>
""".encode()


def _fit(endian: Endian = Endian.LITTLE, extra: Sequence[Any] = ()) -> bytes:
    track = [tuple(map(float, _coordinates(index))) for index in range(POINTS)]
    file_id = FileIdMessage()
    file_id.type = FileType.ACTIVITY
    file_id.serial_number = 3412345678
    messages: list[Any] = [file_id]
    for index, (lat, lon) in enumerate(track):
        record = RecordMessage()
        record.timestamp = FIT_START_MS + index * 10_000
        record.position_lat, record.position_long = lat, lon
        record.heart_rate = 120 + index
        messages.append(record)
    lap = LapMessage()
    session = SessionMessage()
    for summary in (lap, session):
        summary.timestamp = FIT_START_MS + POINTS * 10_000
        summary.start_time = FIT_START_MS
        summary.start_position_lat, summary.start_position_long = track[0]
    lap.end_position_lat, lap.end_position_long = track[-1]
    session.sport = Sport.RUNNING
    session.nec_lat, session.nec_long = track[-1]
    session.swc_lat, session.swc_long = track[0]
    builder = FitFileBuilder(auto_define=True, min_string_size=20)
    for message in [*messages, lap, session, *extra]:
        message.endian = endian
        builder.add(message)
    return bytes(builder.build().to_bytes())


def _fit_messages(data: bytes) -> list[Any]:
    with fitdecode.FitReader(io.BytesIO(data), check_crc=fitdecode.CrcCheck.RAISE) as reader:
        return [frame for frame in reader if isinstance(frame, fitdecode.FitDataMessage)]


def _fit_pairs(data: bytes, box: bool = False) -> list[tuple[float, float]]:
    pairs = []
    for message in _fit_messages(data):
        values = {field.name: field.raw_value for field in message.fields}
        for name, value in values.items():
            stem = name.removesuffix("_lat")
            if stem != name and (stem in ("nec", "swc")) == box:
                pairs.append((value * 180 / 2**31, values[f"{stem}_long"] * 180 / 2**31))
    return pairs


def _fit_everything_else(data: bytes) -> list[tuple[str, str, Any]]:
    return [
        (message.name, field.name, field.raw_value)
        for message in _fit_messages(data)
        for field in message.fields
        if field.units != "semicircles"
    ]


def _fit_extras() -> list[Any]:
    unknown_field = Field(field_id=0, base_type=BaseType.UINT8, size=1)
    unknown_field.set_value(0, 7)
    developer = DeveloperDataIdMessage()
    developer.developer_data_index = 0
    developer.application_id = bytes(range(16))
    description = FieldDescriptionMessage()
    description.developer_data_index = 0
    description.field_definition_number = 0
    description.fit_base_type_id = BaseType.UINT8.value
    description.field_name = "home"
    developer_field = DeveloperField(
        field_id=0, name="home", base_type=BaseType.UINT8, size=1, developer_data_index=0
    )
    developer_field.set_value(0, 3)
    record = RecordMessage()
    record.timestamp = FIT_START_MS + POINTS * 10_000
    record.developer_fields = [developer_field]
    profile = UserProfileMessage()
    profile.friendly_name = "Runner"
    activity = ActivityMessage()
    activity.timestamp = FIT_START_MS + POINTS * 10_000
    activity.local_timestamp = 1_141_200_000
    return [
        DataMessage(global_id=65290, name="unknown", fields=[unknown_field]),
        developer,
        description,
        record,
        profile,
        activity,
    ]


def _half_position() -> Any:
    record = RecordMessage()
    record.timestamp = FIT_START_MS + POINTS * 10_000
    record.position_lat = START_LAT
    return record


def _half_box() -> Any:
    session = SessionMessage()
    session.timestamp = FIT_START_MS + POINTS * 10_000
    session.nec_lat, session.nec_long = START_LAT, START_LON
    return session


def _raw_fit(fields: Sequence[tuple[int, int, int]], values: bytes) -> bytes:
    definition = struct.pack("<BBBHB", 0x40, 0, 0, FIT_RECORD, len(fields))
    definition += b"".join(bytes(field) for field in fields)
    body = definition + b"\x00" + values
    data = struct.pack("<BBHI4s", 12, 0x20, 2100, len(body), b".FIT") + body
    return data + struct.pack("<H", compute_crc(data))


class _NearlyStillFirst(random.Random):
    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self._first = [1.0, 1e-4, 0.0, 0.0]

    def gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        return self._first.pop(0) if self._first else super().gauss(mu, sigma)


def _local(element: Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _coordinate_texts(data: bytes) -> list[tuple[str, str]]:
    root = ElementTree.fromstring(data)
    pairs = [
        (node.attrib["lat"], node.attrib["lon"]) for node in root.iter() if "lat" in node.attrib
    ]
    for node in root.iter():
        if _local(node) == "Position":
            values = {_local(child): (child.text or "").strip() for child in node}
            pairs.append((values["LatitudeDegrees"], values["LongitudeDegrees"]))
    return pairs


def _pairs(data: bytes) -> list[tuple[float, float]]:
    return [(float(lat), float(lon)) for lat, lon in _coordinate_texts(data)]


def _bounds(data: bytes) -> list[dict[str, float]]:
    root = ElementTree.fromstring(data)
    return [
        {key: float(value) for key, value in node.attrib.items()}
        for node in root.iter()
        if _local(node) == "bounds"
    ]


def _mask(data: bytes) -> bytes:
    return re.sub(rb"-?\d+\.\d{4,}", b"#", data)


def _kilometres(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


@pytest.mark.parametrize("source", [_gpx(), _tcx()], ids=["gpx", "tcx"])
def test_anonymize_moves_every_position_and_keeps_everything_else(source):
    result = anonymize(source, rng=random.Random(7))

    before, after = load(source).records, load(result.data).records
    assert after["distance"].to_list() == pytest.approx(before["distance"].to_list(), abs=0.5)
    assert after["timestamp"].to_list() == before["timestamp"].to_list()
    assert after["heart_rate"].to_list() == before["heart_rate"].to_list()
    original, shifted = _pairs(source), _pairs(result.data)
    assert len(shifted) == len(original) == result.positions
    assert not set(original) & set(shifted)
    assert _mask(result.data) == _mask(source)
    assert {
        len(text.partition(".")[2]) for pair in _coordinate_texts(result.data) for text in pair
    } == {7}
    lats, lons = zip(*shifted, strict=True)
    extremes = {"minlat": min(lats), "maxlat": max(lats), "minlon": min(lons), "maxlon": max(lons)}
    assert len(_bounds(result.data)) == len(_bounds(source))
    for bounds in _bounds(result.data):
        assert bounds == pytest.approx(extremes, abs=1e-7)


@pytest.mark.parametrize("endian", [Endian.LITTLE, Endian.BIG], ids=["little", "big"])
def test_anonymize_moves_every_fit_position_and_keeps_every_other_byte(endian):
    source = _fit(endian, _fit_extras())

    result = anonymize(source, rng=random.Random(7))

    before, after = load(source).records, load(result.data).records
    assert after["distance"].to_list() == pytest.approx(before["distance"].to_list(), abs=0.5)
    assert after["timestamp"].to_list() == before["timestamp"].to_list()
    assert after["heart_rate"].to_list() == before["heart_rate"].to_list()
    original, shifted = _fit_pairs(source), _fit_pairs(result.data)
    assert len(shifted) == len(original) == result.positions == FIT_POSITIONS
    assert not set(original) & set(shifted)
    assert _kilometres(original[0], shifted[0]) >= 1000
    assert all(abs(lat) < 60 and abs(lon) < 150 for lat, lon in shifted)
    assert _fit_everything_else(result.data) == _fit_everything_else(source)
    assert len(result.data) == len(source)
    changed = sum(a != b for a, b in zip(source, result.data, strict=True))
    assert changed <= 8 * (FIT_POSITIONS + FIT_BOX_CORNERS) + 2


def test_anonymize_leaves_a_wrong_fit_crc_as_it_was():
    source = _fit()
    wrong = bytes(byte ^ 0xFF for byte in source[-2:])

    result = anonymize(source[:-2] + wrong, rng=random.Random(7))

    assert result.data[-2:] == wrong
    assert result.data[:-2] != source[:-2]


def test_anonymize_turns_a_fit_bounding_box_into_a_box_around_the_shifted_track():
    source = _fit()
    ((north, east), (south, west)) = _fit_pairs(source, box=True)
    diagonal = _kilometres((north, east), (south, west))

    for seed in range(40):
        shifted = anonymize(source, rng=random.Random(seed)).data
        ((north, east), (south, west)) = _fit_pairs(shifted, box=True)
        assert all(
            south - 1e-6 <= lat <= north + 1e-6 and west - 1e-6 <= lon <= east + 1e-6
            for lat, lon in _fit_pairs(shifted)
        )
        assert diagonal * 0.999 <= _kilometres((north, east), (south, west)) <= diagonal * 1.415


def test_anonymize_names_what_a_fit_file_still_holds():
    assert anonymize(_fit(), rng=random.Random(7)).identifying == (Identifying.SERIAL,)
    assert anonymize(_fit(extra=_fit_extras()), rng=random.Random(7)).identifying == (
        Identifying.NAMES,
        Identifying.SERIAL,
        Identifying.TIME_ZONE,
        Identifying.ATHLETE,
        Identifying.UNKNOWN,
        Identifying.DEVELOPER,
    )


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (_fit()[:-20], "unreadable FIT file"),
        (_fit() + b"junk" * 4, "unreadable FIT file"),
        (_fit(extra=[_half_position()]), "only one coordinate"),
        (_fit(extra=[_half_box()]), "only one corner"),
        (_raw_fit([(253, 4, FIT_UINT32)], struct.pack("<I", 1000)), "no positions"),
        (
            _raw_fit([(0, 2, FIT_SINT16), (1, 4, FIT_SINT32)], struct.pack("<hi", 5, FIT_HOME[1])),
            "2 bytes, not 4",
        ),
        (
            _raw_fit(
                [(0, 4, FIT_SINT32), (1, 4, FIT_SINT32)] * 2, struct.pack("<4i", *FIT_HOME * 2)
            ),
            "could not be shifted",
        ),
        (
            _raw_fit(
                [(0, 4, FIT_SINT32), (1, 4, FIT_SINT32), (3, 0, 2)], struct.pack("<2i", *FIT_HOME)
            ),
            "unreadable FIT file",
        ),
    ],
    ids=[
        "truncated",
        "trailing bytes",
        "half a position",
        "half a bounding box",
        "no positions",
        "two-byte latitude",
        "position defined twice",
        "zero-size field",
    ],
)
def test_anonymize_refuses_a_fit_file_it_cannot_shift_completely(source, reason):
    with pytest.raises(ActivityFileError, match=reason):
        anonymize(source, rng=random.Random(7))


def test_anonymize_refuses_a_position_with_a_second_latitude():
    source = _tcx().replace(
        b"<t:Position>", b"<t:Position><t:LatitudeDegrees>55.9</t:LatitudeDegrees>", 1
    )

    with pytest.raises(ActivityFileError, match="more than one latitude"):
        anonymize(source, rng=random.Random(7))


@pytest.mark.parametrize(
    ("start_lat", "latitude_limit"), [(START_LAT, 60.0), (60.17, 90.0)], ids=["55N", "60N"]
)
def test_anonymize_lands_far_away_and_clear_of_the_poles_and_the_antimeridian(
    start_lat, latitude_limit
):
    source = _tcx(start_lat)
    start = _pairs(source)[0]

    for seed in range(40):
        shifted = _pairs(anonymize(source, rng=_NearlyStillFirst(seed)).data)
        assert _kilometres(start, shifted[0]) >= 1000
        assert all(abs(lat) < latitude_limit and abs(lon) < 150 for lat, lon in shifted)

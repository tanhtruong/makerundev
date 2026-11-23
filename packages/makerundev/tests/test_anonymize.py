import math
import random
import re
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree
from makerundev import ActivityFileError, load
from makerundev.io import anonymize

START_LAT = 55.6761234
START_LON = 12.5683371
POINTS = 50
EARTH_RADIUS_KM = 6371.0088


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

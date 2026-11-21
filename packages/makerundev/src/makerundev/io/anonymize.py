import itertools
import math
import random
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, NamedTuple
from xml.parsers.expat import ExpatError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from makerundev.errors import ActivityFileError
from makerundev.io.xml import local_name, strip_namespace
from makerundev.model import EARTH_RADIUS_M

MIN_SHIFT_M = 1_000_000.0
MAX_LANDING_LATITUDE = 60.0
MAX_LANDING_LONGITUDE = 150.0
MAX_ATTEMPTS = 1000

_START_TAG = re.compile(rb"""<[^\s/>]+(?:\s+[^\s=/>]+\s*=\s*(?:"[^"]*"|'[^']*'))*\s*/?>""")
_ATTRIBUTE = re.compile(rb"""\s([^\s=/>]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_NUMBER = re.compile(rb"\s*([-+]?\d+(?:\.(\d*))?)\s*")
_OFFSET = re.compile(rb"[+-](?!00:00)\d\d:\d\d\s*")
_BOUNDS = ("minlat", "maxlat", "minlon", "maxlon")
_AXES = {"LatitudeDegrees": "latitude", "LongitudeDegrees": "longitude"}

Point = tuple[float, float]
Vector = tuple[float, float, float]
Matrix = tuple[Vector, Vector, Vector]


class Identifying(StrEnum):
    NAMES = "names and notes"
    AUTHOR = "author and links"
    SERIAL = "device serial"
    TIME_ZONE = "time zone"


_IDENTIFYING_ELEMENTS = {
    "name": Identifying.NAMES,
    "desc": Identifying.NAMES,
    "cmt": Identifying.NAMES,
    "Notes": Identifying.NAMES,
    "author": Identifying.AUTHOR,
    "Author": Identifying.AUTHOR,
    "email": Identifying.AUTHOR,
    "link": Identifying.AUTHOR,
    "UnitId": Identifying.SERIAL,
}


class Anonymized(NamedTuple):
    data: bytes
    positions: int
    identifying: tuple[Identifying, ...]


@dataclass(frozen=True)
class _Number:
    start: int
    end: int
    decimals: int
    value: float


class _Position(NamedTuple):
    latitude: _Number
    longitude: _Number


@dataclass
class _OpenElement:
    name: str
    content_start: int
    line: int
    coordinates: dict[str, _Number | None] = field(default_factory=dict)


def shift_positions(data: bytes, rng: random.Random) -> Anonymized:
    scan = _Scan(data)
    if not scan.positions:
        raise ActivityFileError("the file has no positions to shift")
    points = _rotate_far(
        [(position.latitude.value, position.longitude.value) for position in scan.positions], rng
    )
    replacements = [
        (number, value)
        for position, point in zip(scan.positions, points, strict=True)
        for number, value in zip(position, point, strict=True)
    ]
    latitudes = [latitude for latitude, _ in points]
    longitudes = [longitude for _, longitude in points]
    extremes = {
        "minlat": min(latitudes),
        "maxlat": max(latitudes),
        "minlon": min(longitudes),
        "maxlon": max(longitudes),
    }
    replacements += [(number, extremes[name]) for name, number in scan.bounds]
    decimals = max(number.decimals for position in scan.positions for number in position)
    shifted = _replace(data, replacements, decimals)
    _check_every_position_moved(data, shifted, len(scan.positions))
    identifying = tuple(label for label in Identifying if label in scan.identifying)
    return Anonymized(shifted, len(points), identifying)


class _Scan:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.positions: list[_Position] = []
        self.bounds: list[tuple[str, _Number]] = []
        self.identifying: set[Identifying] = set()
        self._stack: list[_OpenElement] = []
        self._expat: Any = ElementTree.DefusedXMLParser().parser
        self._expat.StartElementHandler = self._start
        self._expat.EndElementHandler = self._end
        try:
            self._expat.Parse(data, True)
        except (ExpatError, DefusedXmlException) as error:
            raise ActivityFileError(f"unreadable XML: {error}") from error

    def _start(self, name: str, _attributes: list[str]) -> None:
        start = self._expat.CurrentByteIndex
        line = self._expat.CurrentLineNumber
        tag = _START_TAG.match(self.data, start)
        if tag is None:
            raise ActivityFileError(f"unreadable start tag on line {line}")
        attributes = self._attributes(start, tag.end())
        local = strip_namespace(name)
        self._add_position(attributes.get("lat"), attributes.get("lon"), line)
        if local == "bounds":
            self.bounds += [
                (key, number) for key in _BOUNDS if (number := attributes.get(key)) is not None
            ]
        if local in _IDENTIFYING_ELEMENTS:
            self.identifying.add(_IDENTIFYING_ELEMENTS[local])
        self._stack.append(_OpenElement(local, tag.end(), line))

    def _end(self, _name: str) -> None:
        element = self._stack.pop()
        end = max(self._expat.CurrentByteIndex, element.content_start)
        content = self.data[element.content_start : end]
        axis = _AXES.get(element.name)
        if axis is not None and self._stack:
            parent = self._stack[-1]
            if axis in parent.coordinates:
                raise ActivityFileError(f"position on line {parent.line} has more than one {axis}")
            parent.coordinates[axis] = self._number(element.content_start, content)
        if element.name.lower() == "time" and _OFFSET.search(content):
            self.identifying.add(Identifying.TIME_ZONE)
        coordinates = element.coordinates
        self._add_position(coordinates.get("latitude"), coordinates.get("longitude"), element.line)

    def _attributes(self, start: int, end: int) -> dict[str, _Number | None]:
        numbers = {}
        for match in _ATTRIBUTE.finditer(self.data, start, end):
            group = 2 if match[2] is not None else 3
            numbers[match[1].decode()] = self._number(match.start(group), match[group])
        return numbers

    def _add_position(self, latitude: _Number | None, longitude: _Number | None, line: int) -> None:
        if latitude is not None and longitude is not None:
            self.positions.append(_Position(latitude, longitude))
        elif latitude is not None or longitude is not None:
            raise ActivityFileError(f"position on line {line} has only one coordinate")

    @staticmethod
    def _number(offset: int, raw: bytes) -> _Number | None:
        match = _NUMBER.fullmatch(raw)
        if match is None:
            return None
        return _Number(
            offset + match.start(1),
            offset + match.end(1),
            len(match[2] or b""),
            float(match[1]),
        )


def _replace(data: bytes, replacements: list[tuple[_Number, float]], decimals: int) -> bytes:
    parts = []
    position = 0
    for number, value in sorted(replacements, key=lambda item: item[0].start):
        parts += [
            data[position : number.start],
            f"{value:.{max(number.decimals, decimals)}f}".encode(),
        ]
        position = number.end
    parts.append(data[position:])
    return b"".join(parts)


def _check_every_position_moved(original: bytes, shifted: bytes, positions: int) -> None:
    before, before_values = _parsed_positions(original)
    after, after_values = _parsed_positions(shifted)
    if (
        before_values != 2 * positions
        or after_values != before_values
        or len(after) != len(before)
        or set(before) & set(after)
    ):
        raise ActivityFileError("some positions could not be shifted, so nothing was written")


def _parsed_positions(data: bytes) -> tuple[list[Point], int]:
    points: list[Point] = []
    values = 0
    for node in ElementTree.fromstring(data).iter():
        latitudes = [child.text for child in node if local_name(child) == "LatitudeDegrees"]
        longitudes = [child.text for child in node if local_name(child) == "LongitudeDegrees"]
        candidates = [(node.get("lat"), node.get("lon"))]
        if len(latitudes) == len(longitudes) == 1:
            candidates.append((latitudes[0], longitudes[0]))
        values += sum(
            _float(value) is not None
            for value in (node.get("lat"), node.get("lon"), *latitudes, *longitudes)
        )
        for latitude, longitude in candidates:
            point = (_float(latitude), _float(longitude))
            if point[0] is not None and point[1] is not None:
                points.append((point[0], point[1]))
    return points, values


def _float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _rotate_far(points: list[Point], rng: random.Random) -> list[Point]:
    confine_latitude = _largest(points, 0) < MAX_LANDING_LATITUDE
    confine_longitude = not _crosses_antimeridian(points)
    start = _vector(points[0])
    for _ in range(MAX_ATTEMPTS):
        matrix = _random_rotation(rng)
        if _metres(start, _apply(matrix, start)) < MIN_SHIFT_M:
            continue
        rotated = [_point(_apply(matrix, _vector(point))) for point in points]
        if confine_latitude and _largest(rotated, 0) >= MAX_LANDING_LATITUDE:
            continue
        if confine_longitude and _largest(rotated, 1) >= MAX_LANDING_LONGITUDE:
            continue
        return rotated
    raise ActivityFileError(
        "could not find a shift that keeps the track clear of the poles and the antimeridian"
    )


def _largest(points: list[Point], axis: int) -> float:
    return max(abs(point[axis]) for point in points)


def _crosses_antimeridian(points: list[Point]) -> bool:
    return any(abs(a[1] - b[1]) > 180 for a, b in itertools.pairwise(points))


def _random_rotation(rng: random.Random) -> Matrix:
    w, x, y, z = (rng.gauss(0.0, 1.0) for _ in range(4))
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / norm, x / norm, y / norm, z / norm
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )


def _apply(matrix: Matrix, vector: Vector) -> Vector:
    a, b, c = (sum(m * v for m, v in zip(row, vector, strict=True)) for row in matrix)
    return a, b, c


def _vector(point: Point) -> Vector:
    latitude, longitude = map(math.radians, point)
    return (
        math.cos(latitude) * math.cos(longitude),
        math.cos(latitude) * math.sin(longitude),
        math.sin(latitude),
    )


def _point(vector: Vector) -> Point:
    x, y, z = vector
    return math.degrees(math.asin(max(-1.0, min(1.0, z)))), math.degrees(math.atan2(y, x))


def _metres(a: Vector, b: Vector) -> float:
    dot = max(-1.0, min(1.0, sum(p * q for p, q in zip(a, b, strict=True))))
    return EARTH_RADIUS_M * math.acos(dot)

import io
import itertools
import random
import struct
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, NamedTuple

import fitdecode
from fitdecode.utils import compute_crc

from makerundev.errors import ActivityFileError
from makerundev.io.anonymize import Anonymized, Identifying, Point, rotate_far
from makerundev.io.fit import SEMICIRCLE_TO_DEGREES

_INVALID = 0x7FFFFFFF
_COORDINATE_BYTES = 4
_CRC_BYTES = 2
_BOX_CORNERS = ("nec", "swc")
_DEVICE_CLOCK_FIELDS = {"time_zone_offset", "time_offset", "utc_offset"}
_UNREADABLE = (
    fitdecode.FitError,
    struct.error,
    AssertionError,
    IndexError,
    KeyError,
    TypeError,
    ValueError,
)


@dataclass(frozen=True)
class _Coordinate:
    offset: int
    byte_order: Literal["little", "big"]
    raw: int

    @property
    def degrees(self) -> float:
        return self.raw * SEMICIRCLE_TO_DEGREES


class _Position(NamedTuple):
    latitude: _Coordinate
    longitude: _Coordinate


class _Box(NamedTuple):
    north_east: _Position
    south_west: _Position


class _Checksum(NamedTuple):
    file_start: int
    offset: int


@dataclass
class _Scan:
    positions: list[_Position] = field(default_factory=list)
    boxes: list[_Box] = field(default_factory=list)
    matching_checksums: list[_Checksum] = field(default_factory=list)
    identifying: set[Identifying] = field(default_factory=set)

    @property
    def coordinates(self) -> list[_Coordinate]:
        boxed = [position for box in self.boxes for position in box]
        return [coordinate for position in [*self.positions, *boxed] for coordinate in position]


def shift_fit_positions(data: bytes, rng: random.Random) -> Anonymized:
    scan = _scan(data)
    if not scan.positions:
        raise ActivityFileError("the file has no positions to shift")
    corners = [corner for box in scan.boxes for corner in _corners(box)]
    points = rotate_far(
        [
            *(
                (position.latitude.degrees, position.longitude.degrees)
                for position in scan.positions
            ),
            *corners,
        ],
        rng,
    )
    shifted = bytearray(data)
    for position, point in zip(scan.positions, points, strict=False):
        _write(shifted, position, point)
    rotated_corners = itertools.batched(points[len(scan.positions) :], 4)
    for box, rotated in zip(scan.boxes, rotated_corners, strict=True):
        latitudes, longitudes = zip(*rotated, strict=True)
        _write(shifted, box.north_east, (max(latitudes), max(longitudes)))
        _write(shifted, box.south_west, (min(latitudes), min(longitudes)))
    for checksum in scan.matching_checksums:
        crc = compute_crc(shifted, start=checksum.file_start, end=checksum.offset)
        shifted[checksum.offset : checksum.offset + _CRC_BYTES] = struct.pack("<H", crc)
    result = bytes(shifted)
    _check_every_position_moved(data, result, scan)
    identifying = tuple(label for label in Identifying if label in scan.identifying)
    return Anonymized(result, len(scan.positions), identifying)


def _scan(data: bytes) -> _Scan:
    scan = _Scan()
    file_start = 0
    for frame in _frames(data, keep_raw_chunks=True):
        if isinstance(frame, fitdecode.FitHeader):
            file_start = frame.chunk.offset
        elif isinstance(frame, fitdecode.FitCRC):
            if frame.matched:
                scan.matching_checksums.append(_Checksum(file_start, frame.chunk.offset))
        elif isinstance(frame, fitdecode.FitDataMessage):
            _scan_message(frame, scan)
    return scan


def _frames(data: bytes, *, keep_raw_chunks: bool) -> Iterator[Any]:
    try:
        with fitdecode.FitReader(
            io.BytesIO(data),
            check_crc=fitdecode.CrcCheck.READONLY,
            error_handling=fitdecode.ErrorHandling.IGNORE,
            keep_raw_chunks=keep_raw_chunks,
        ) as reader:
            yield from reader
    except _UNREADABLE as error:
        raise ActivityFileError(f"unreadable FIT file: {error!r}") from error


def _scan_message(frame: Any, scan: _Scan) -> None:
    definition = frame.def_mesg
    if definition.dev_field_defs:
        scan.identifying.add(Identifying.DEVELOPER)
    if frame.name == "user_profile":
        scan.identifying.add(Identifying.ATHLETE)
    byte_order: Literal["little", "big"] = "little" if definition.endian == "<" else "big"
    start = frame.chunk.offset
    offset = 1
    coordinates: dict[str, _Coordinate] = {}
    for field_definition in definition.field_defs:
        known = field_definition.field
        if known is None:
            scan.identifying.add(Identifying.UNKNOWN)
        elif known.units == "semicircles":
            if field_definition.size != _COORDINATE_BYTES:
                raise ActivityFileError(
                    f"position at byte {start + offset} is {field_definition.size} bytes,"
                    f" not {_COORDINATE_BYTES}"
                )
            raw = int.from_bytes(
                frame.chunk.bytes[offset : offset + _COORDINATE_BYTES], byte_order, signed=True
            )
            if raw != _INVALID:
                coordinates[known.name] = _Coordinate(start + offset, byte_order, raw)
        elif known.name == "serial_number":
            scan.identifying.add(Identifying.SERIAL)
        elif field_definition.base_type.name == "string":
            scan.identifying.add(Identifying.NAMES)
        elif known.name == "local_timestamp" or (
            frame.name == "device_settings" and known.name in _DEVICE_CLOCK_FIELDS
        ):
            scan.identifying.add(Identifying.TIME_ZONE)
        offset += field_definition.size
    positions = _positions(coordinates, start)
    corners = [positions.pop(name, None) for name in _BOX_CORNERS]
    north_east, south_west = corners
    if north_east is not None and south_west is not None:
        scan.boxes.append(_Box(north_east, south_west))
    elif north_east is not None or south_west is not None:
        raise ActivityFileError(f"bounding box at byte {start} has only one corner")
    scan.positions += positions.values()


def _positions(coordinates: dict[str, _Coordinate], start: int) -> dict[str, _Position]:
    names = dict.fromkeys(name.removesuffix("_lat").removesuffix("_long") for name in coordinates)
    positions = {}
    for name in names:
        latitude, longitude = coordinates.get(f"{name}_lat"), coordinates.get(f"{name}_long")
        if latitude is None or longitude is None:
            raise ActivityFileError(f"position at byte {start} has only one coordinate")
        positions[name] = _Position(latitude, longitude)
    return positions


def _corners(box: _Box) -> list[Point]:
    latitudes = (box.north_east.latitude.degrees, box.south_west.latitude.degrees)
    longitudes = (box.north_east.longitude.degrees, box.south_west.longitude.degrees)
    return list(itertools.product(latitudes, longitudes))


def _write(data: bytearray, position: _Position, point: Point) -> None:
    for coordinate, degrees in zip(position, point, strict=True):
        raw = round(degrees / SEMICIRCLE_TO_DEGREES)
        data[coordinate.offset : coordinate.offset + _COORDINATE_BYTES] = raw.to_bytes(
            _COORDINATE_BYTES, coordinate.byte_order, signed=True
        )


def _check_every_position_moved(original: bytes, shifted: bytes, scan: _Scan) -> None:
    restored = bytearray(shifted)
    patched = [(coordinate.offset, _COORDINATE_BYTES) for coordinate in scan.coordinates]
    patched += [(checksum.offset, _CRC_BYTES) for checksum in scan.matching_checksums]
    for offset, size in patched:
        restored[offset : offset + size] = original[offset : offset + size]
    before, after = _decoded_coordinates(original), _decoded_coordinates(shifted)
    found = sum(map(len, before))
    if (
        restored != original
        or found != len(scan.coordinates)
        or sum(map(len, after)) != found
        or any(then == now for then, now in zip(before, after, strict=False))
    ):
        raise ActivityFileError("some positions could not be shifted, so nothing was written")


def _decoded_coordinates(data: bytes) -> list[tuple[int, ...]]:
    messages = []
    for frame in _frames(data, keep_raw_chunks=False):
        if not isinstance(frame, fitdecode.FitDataMessage):
            continue
        coordinates = tuple(
            decoded.raw_value
            for decoded in frame.fields
            if decoded.units == "semicircles" and decoded.raw_value is not None
        )
        if coordinates:
            messages.append(coordinates)
    return messages

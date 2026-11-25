import gzip
import math
from io import BytesIO
from pathlib import Path

from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer

EXTENT = 4096
MAX_ZOOM = 15
HARBOUR = (12.56, 55.67)
WORLD_E7 = {
    "min_lon_e7": -1_800_000_000,
    "min_lat_e7": -850_511_287,
    "max_lon_e7": 1_800_000_000,
    "max_lat_e7": 850_511_287,
    "center_zoom": 0,
    "center_lon_e7": 0,
    "center_lat_e7": 0,
}


def _varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _field(number: int, payload: bytes) -> bytes:
    return _varint(number << 3 | 2) + _varint(len(payload)) + payload


def _number(number: int, value: int) -> bytes:
    return _varint(number << 3) + _varint(value)


def _zigzag(value: int) -> int:
    return (value << 1) ^ (value >> 31)


def _commands(*values: int) -> bytes:
    return b"".join(_varint(value) for value in values)


def _string(text: str) -> bytes:
    return _field(1, text.encode())


def _earth() -> bytes:
    geometry = _commands(
        1 | 1 << 3,
        _zigzag(0),
        _zigzag(0),
        2 | 3 << 3,
        _zigzag(EXTENT),
        _zigzag(0),
        _zigzag(0),
        _zigzag(EXTENT),
        _zigzag(-EXTENT),
        _zigzag(0),
        7 | 1 << 3,
    )
    feature = _number(3, 3) + _field(4, geometry)
    return _number(15, 2) + _field(1, b"earth") + _field(2, feature) + _number(5, EXTENT)


def _place(x: int, y: int) -> bytes:
    geometry = _commands(1 | 1 << 3, _zigzag(x), _zigzag(y))
    feature = _field(2, _commands(0, 0, 1, 1)) + _number(3, 1) + _field(4, geometry)
    return (
        _number(15, 2)
        + _field(1, b"places")
        + _field(2, feature)
        + _field(3, b"kind")
        + _field(3, b"name")
        + _field(4, _string("locality"))
        + _field(4, _string("Harbour"))
        + _number(5, EXTENT)
    )


def _tile_position(z: int, lon: float, lat: float) -> tuple[int, int, int, int]:
    scale = 2**z * EXTENT
    world_x = (lon + 180) / 360 * scale
    world_y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * scale
    x, y = int(world_x // EXTENT), int(world_y // EXTENT)
    return x, y, int(world_x - x * EXTENT), int(world_y - y * EXTENT)


def pmtiles_bytes() -> bytes:
    buffer = BytesIO()
    writer = Writer(buffer)
    for z in range(MAX_ZOOM + 1):
        x, y, label_x, label_y = _tile_position(z, *HARBOUR)
        tile = _field(3, _earth()) + _field(3, _place(label_x, label_y))
        writer.write_tile(zxy_to_tileid(z, x, y), gzip.compress(tile, mtime=0))
    header = {"tile_type": TileType.MVT, "tile_compression": Compression.GZIP} | WORLD_E7
    writer.finalize(header, {"name": "Protomaps Basemap", "type": "baselayer"})
    return buffer.getvalue()


def write_pmtiles(path: Path) -> bytes:
    data = pmtiles_bytes()
    path.write_bytes(data)
    return data

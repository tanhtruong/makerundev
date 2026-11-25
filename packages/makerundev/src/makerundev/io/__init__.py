import os
import random
import re
import zipfile
import zlib
from collections.abc import Callable
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import NamedTuple
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from makerundev.errors import ActivityFileError
from makerundev.io.anonymize import Anonymized, Identifying, shift_positions
from makerundev.io.anonymize_fit import shift_fit_positions
from makerundev.io.fit import read_fit
from makerundev.io.gpx import read_gpx
from makerundev.io.tcx import read_tcx
from makerundev.io.xml import local_name
from makerundev.model import Activity

MAX_DECOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_ZIP_FILES = 16
MAX_ZIP_DIRECTORY_BYTES = 64 * 1024

_ZIP_LOCAL_HEADER = b"PK\x03\x04"
_ZIP_END = b"PK\x05\x06"
_ZIP_END_SIZE = 22
_ZIP_MAX_COMMENT = 0xFFFF
_ZIP64_LOCATOR = b"PK\x06\x07"
_ZIP64_LOCATOR_SIZE = 20
_ZIP_ENCRYPTED = 0x1
_ZIP_METHODS = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})
_ZIP_READ_CHUNK = 1024 * 1024

_XML_ROOT = re.compile(
    rb"(?:\xef\xbb\xbf)?\s*"
    rb"(?:(?:<\?.*?\?>|<!--.*?-->|<!DOCTYPE[^>\[]*(?:\[.*?\])?\s*>)\s*)*"
    rb"<([\w.:-]+)",
    re.S,
)
_XML_READERS: dict[str, Callable[[Element], Activity]] = {
    "gpx": read_gpx,
    "TrainingCenterDatabase": read_tcx,
}

__all__ = [
    "ActivityFileError",
    "Anonymized",
    "Identifying",
    "ZipEntry",
    "anonymize",
    "load",
    "unzip",
]


class ZipEntry(NamedTuple):
    name: str
    data: bytes


def load(source: str | os.PathLike[str] | bytes) -> Activity:
    data = _unwrap(source if isinstance(source, bytes) else Path(source).read_bytes())
    if _is_fit(data):
        return read_fit(data)
    if _xml_root(data) is not None:
        return _read_xml(data)
    raise ActivityFileError("unsupported file: expected FIT, GPX or TCX")


def anonymize(data: bytes, *, rng: random.Random | None = None) -> Anonymized:
    data = _unwrap(data)
    rng = rng or random.SystemRandom()
    if _is_fit(data):
        return shift_fit_positions(data, rng)
    if data[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in data[:4]:
        raise ActivityFileError("UTF-16 and UTF-32 files are not supported; save it as UTF-8")
    if _xml_root(data) not in _XML_READERS:
        raise ActivityFileError("unsupported file: expected FIT, GPX or TCX")
    return shift_positions(data, rng)


def _unwrap(data: bytes) -> bytes:
    entry = unzip(data)
    if entry is not None:
        data = entry.data
    if data[:2] == b"\x1f\x8b":
        data = _gunzip(data)
    return data


def unzip(data: bytes) -> ZipEntry | None:
    if data[:4] != _ZIP_LOCAL_HEADER:
        return None
    _check_zip_directory(data)
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            info, content = _only_activity(archive)
    except ActivityFileError:
        raise
    except (
        zipfile.BadZipFile,
        zlib.error,
        EOFError,
        NotImplementedError,
        ValueError,
        OSError,
    ) as error:
        raise ActivityFileError(f"corrupt ZIP data: {error}") from error
    return ZipEntry(PurePosixPath(info.filename.replace("\\", "/")).name, content)


def _check_zip_directory(data: bytes) -> None:
    end = len(data) - _ZIP_END_SIZE
    if data[end : end + 4] != _ZIP_END or data[-2:] != b"\x00\x00":
        end = data.rfind(_ZIP_END, max(0, len(data) - _ZIP_END_SIZE - _ZIP_MAX_COMMENT - 1))
    if end < 0 or len(data) < end + _ZIP_END_SIZE:
        raise ActivityFileError("corrupt ZIP data: no end of central directory")
    locator = end - _ZIP64_LOCATOR_SIZE
    if locator >= 0 and data[locator : locator + 4] == _ZIP64_LOCATOR:
        raise ActivityFileError("ZIP64 archives are not supported")
    if int.from_bytes(data[end + 12 : end + 16], "little") > MAX_ZIP_DIRECTORY_BYTES:
        raise ActivityFileError(
            f"ZIP directory is larger than {MAX_ZIP_DIRECTORY_BYTES // 1024} KB"
        )


def _only_activity(archive: zipfile.ZipFile) -> tuple[zipfile.ZipInfo, bytes]:
    files = [info for info in archive.infolist() if not info.is_dir()]
    if len(files) > MAX_ZIP_FILES:
        raise ActivityFileError(f"ZIP holds more than {MAX_ZIP_FILES} files")
    for info in files:
        if info.flag_bits & _ZIP_ENCRYPTED:
            raise ActivityFileError(f"ZIP entry {info.filename} is encrypted")
        if info.compress_type not in _ZIP_METHODS:
            raise ActivityFileError(
                f"ZIP entry {info.filename} uses an unsupported compression method"
            )
    budget = MAX_DECOMPRESSED_BYTES
    activities = []
    for info in files:
        content = _read_entry(archive, info, budget)
        budget -= len(content)
        if _is_activity(content):
            activities.append((info, content))
    if not activities:
        raise ActivityFileError("ZIP holds no FIT, GPX or TCX file")
    if len(activities) > 1:
        raise ActivityFileError(
            "ZIP holds more than one activity file; extract it and import the files"
        )
    return activities[0]


def _read_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo, budget: int) -> bytes:
    content = bytearray()
    with archive.open(info) as entry:
        while chunk := entry.read(_ZIP_READ_CHUNK):
            content += chunk
            if len(content) > budget:
                raise _too_large()
    return bytes(content)


def _is_activity(data: bytes) -> bool:
    return _is_fit(data) or _xml_root(data) in _XML_READERS


def _is_fit(data: bytes) -> bool:
    return len(data) >= 12 and data[8:12] == b".FIT"


def _xml_root(data: bytes) -> str | None:
    match = _XML_ROOT.match(data)
    if match is None:
        return None
    return match[1].rsplit(b":", 1)[-1].decode()


def _read_xml(data: bytes) -> Activity:
    try:
        root = ElementTree.fromstring(data)
    except (ElementTree.ParseError, DefusedXmlException) as error:
        raise ActivityFileError(f"unreadable XML: {error}") from error
    name = local_name(root)
    reader = _XML_READERS.get(name)
    if reader is None:
        raise ActivityFileError(f"unsupported XML document <{name}>")
    return reader(root)


def _gunzip(data: bytes) -> bytes:
    inflater = zlib.decompressobj(wbits=31)
    try:
        out = inflater.decompress(data, MAX_DECOMPRESSED_BYTES)
    except zlib.error as error:
        raise ActivityFileError(f"corrupt gzip data: {error}") from error
    if inflater.unconsumed_tail:
        raise _too_large()
    return out


def _too_large() -> ActivityFileError:
    return ActivityFileError(
        f"decompressed file is larger than {MAX_DECOMPRESSED_BYTES // (1024 * 1024)} MB"
    )

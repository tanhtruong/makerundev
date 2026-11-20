import os
import zlib
from pathlib import Path

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from makerundev.errors import ActivityFileError
from makerundev.io.fit import read_fit
from makerundev.io.gpx import read_gpx
from makerundev.io.tcx import read_tcx
from makerundev.model import Activity

MAX_DECOMPRESSED_BYTES = 256 * 1024 * 1024

__all__ = ["ActivityFileError", "load"]


def load(source: str | os.PathLike[str] | bytes) -> Activity:
    data = source if isinstance(source, bytes) else Path(source).read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = _gunzip(data)
    if len(data) >= 12 and data[8:12] == b".FIT":
        return read_fit(data)
    if data.lstrip(b"\xef\xbb\xbf \t\r\n")[:1] == b"<":
        return _read_xml(data)
    raise ActivityFileError("unsupported file: expected FIT, GPX or TCX")


def _read_xml(data: bytes) -> Activity:
    try:
        root = ElementTree.fromstring(data)
    except (ElementTree.ParseError, DefusedXmlException) as error:
        raise ActivityFileError(f"unreadable XML: {error}") from error
    name = root.tag.rsplit("}", 1)[-1]
    if name == "gpx":
        return read_gpx(root)
    if name == "TrainingCenterDatabase":
        return read_tcx(root)
    raise ActivityFileError(f"unsupported XML document <{name}>")


def _gunzip(data: bytes) -> bytes:
    inflater = zlib.decompressobj(wbits=31)
    try:
        out = inflater.decompress(data, MAX_DECOMPRESSED_BYTES)
    except zlib.error as error:
        raise ActivityFileError(f"corrupt gzip data: {error}") from error
    if inflater.unconsumed_tail:
        raise ActivityFileError("decompressed file is larger than 256 MB")
    return out

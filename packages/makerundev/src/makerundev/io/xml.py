import datetime as dt
from collections.abc import Iterator
from xml.etree.ElementTree import Element

from makerundev.errors import ActivityFileError


def strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def local_name(element: Element) -> str:
    return strip_namespace(element.tag)


def children(element: Element, name: str) -> Iterator[Element]:
    return (child for child in element if local_name(child) == name)


def descendants(element: Element, name: str) -> Iterator[Element]:
    return (node for node in element.iter() if local_name(node) == name)


def find(element: Element, *path: str) -> Element | None:
    current: Element | None = element
    for name in path:
        if current is None:
            return None
        current = next(children(current, name), None)
    return current


def text(element: Element, *path: str) -> str | None:
    node = find(element, *path)
    if node is None or node.text is None:
        return None
    return node.text.strip() or None


def number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as error:
        raise ActivityFileError(f"expected a number, got {value!r}") from error


def timestamp(value: str | None) -> dt.datetime | None:
    if value is None:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as error:
        raise ActivityFileError(f"expected an ISO 8601 time, got {value!r}") from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)

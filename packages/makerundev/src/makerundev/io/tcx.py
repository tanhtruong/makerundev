from typing import Any
from xml.etree.ElementTree import Element

from makerundev.io.xml import children, descendants, find, number, text, timestamp
from makerundev.model import Activity, Sport

TCX_SPORTS = {"running": Sport.RUNNING, "biking": Sport.CYCLING}


def read_tcx(root: Element) -> Activity:
    activity = find(root, "Activities", "Activity")
    sport_name = (activity.get("Sport") or "").lower() if activity is not None else ""
    rows = [_trackpoint(point) for point in descendants(root, "Trackpoint")]
    return Activity.from_rows(
        rows, sport=TCX_SPORTS.get(sport_name, Sport.OTHER), source_format="tcx"
    )


def _trackpoint(point: Element) -> dict[str, Any]:
    run_cadence = _extension(point, "RunCadence")
    return {
        "timestamp": timestamp(text(point, "Time")),
        "latitude": number(text(point, "Position", "LatitudeDegrees")),
        "longitude": number(text(point, "Position", "LongitudeDegrees")),
        "altitude": number(text(point, "AltitudeMeters")),
        "distance": number(text(point, "DistanceMeters")),
        "heart_rate": number(text(point, "HeartRateBpm", "Value")),
        "cadence": run_cadence * 2 if run_cadence is not None else number(text(point, "Cadence")),
        "speed": _extension(point, "Speed"),
        "power": _extension(point, "Watts"),
    }


def _extension(point: Element, name: str) -> float | None:
    extensions = next(children(point, "Extensions"), None)
    if extensions is None:
        return None
    node = next(descendants(extensions, name), None)
    return number(node.text.strip()) if node is not None and node.text else None

from typing import Any
from xml.etree.ElementTree import Element

from makerundev.io.xml import children, descendants, number, text, timestamp
from makerundev.model import Activity, Sport

GPX_SPORTS = {
    "running": Sport.RUNNING,
    "run": Sport.RUNNING,
    "trail_running": Sport.TRAIL_RUNNING,
    "trail running": Sport.TRAIL_RUNNING,
    "walking": Sport.WALKING,
    "walk": Sport.WALKING,
    "hiking": Sport.HIKING,
    "hike": Sport.HIKING,
    "cycling": Sport.CYCLING,
    "biking": Sport.CYCLING,
    "ride": Sport.CYCLING,
    "swimming": Sport.SWIMMING,
    "swim": Sport.SWIMMING,
}


def read_gpx(root: Element) -> Activity:
    tracks = list(children(root, "trk"))
    sport_name = (text(tracks[0], "type") or "").lower() if tracks else ""
    sport = GPX_SPORTS.get(sport_name, Sport.OTHER)
    cadence_factor = 2 if sport.is_running else 1
    rows = [
        _point(point, cadence_factor)
        for track in tracks
        for segment in children(track, "trkseg")
        for point in children(segment, "trkpt")
    ]
    return Activity.from_rows(rows, sport=sport, source_format="gpx")


def _point(point: Element, cadence_factor: int) -> dict[str, Any]:
    cadence = _extension(point, "cad")
    return {
        "timestamp": timestamp(text(point, "time")),
        "latitude": number(point.get("lat")),
        "longitude": number(point.get("lon")),
        "altitude": number(text(point, "ele")),
        "heart_rate": _extension(point, "hr"),
        "cadence": cadence * cadence_factor if cadence is not None else None,
        "power": _extension(point, "power"),
        "temperature": _extension(point, "atemp"),
    }


def _extension(point: Element, name: str) -> float | None:
    node = next(descendants(point, name), None)
    return number(node.text.strip()) if node is not None and node.text else None

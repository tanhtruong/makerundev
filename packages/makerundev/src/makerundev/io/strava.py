import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Any

from makerundev.errors import ActivityFileError
from makerundev.model import Activity, Lap, Sport

STREAM_KEYS = (
    "time",
    "latlng",
    "distance",
    "altitude",
    "velocity_smooth",
    "heartrate",
    "cadence",
    "watts",
    "temp",
)

STRAVA_SPORTS = {
    "Run": Sport.RUNNING,
    "TrailRun": Sport.TRAIL_RUNNING,
    "VirtualRun": Sport.TREADMILL_RUNNING,
    "Walk": Sport.WALKING,
    "Hike": Sport.HIKING,
    "Swim": Sport.SWIMMING,
}

COLUMNS = {
    "distance": "distance",
    "altitude": "altitude",
    "velocity_smooth": "speed",
    "heartrate": "heart_rate",
    "watts": "power",
    "temp": "temperature",
}

Streams = Mapping[str, Any] | Sequence[Mapping[str, Any]]


def read_strava(activity: Mapping[str, Any], streams: Streams) -> Activity:
    data = _stream_data(streams)
    offsets = data.get("time") or []
    if not offsets:
        raise ActivityFileError("the Strava activity has no time stream")
    start = _start(activity)
    positions = data.get("latlng") or []
    sport = _sport(activity, has_positions=bool(positions))
    cadence_factor = 2 if sport.is_running else 1
    rows = []
    for index, offset in enumerate(offsets):
        position = _at(positions, index)
        cadence = _at(data.get("cadence"), index)
        row: dict[str, Any] = {
            "timestamp": start + dt.timedelta(seconds=offset) if offset is not None else None,
            "latitude": position[0] if position else None,
            "longitude": position[1] if position else None,
            "cadence": cadence * cadence_factor if cadence is not None else None,
        }
        for key, column in COLUMNS.items():
            row[column] = _at(data.get(key), index)
        rows.append(row)
    name = str(activity.get("name") or "").strip() or None
    return Activity.from_rows(
        rows,
        sport=sport,
        source_format="strava",
        start_time=start,
        name=name,
        laps=strava_laps(activity),
    )


def strava_laps(activity: Mapping[str, Any]) -> tuple[Lap, ...]:
    listed = activity.get("laps")
    if not isinstance(listed, list):
        return ()
    laps = []
    for lap in listed:
        if not isinstance(lap, Mapping):
            continue
        try:
            start = _start(lap)
        except ActivityFileError:
            continue
        laps.append(
            Lap(
                start_time=start,
                elapsed_s=_number(lap.get("elapsed_time")),
                distance_m=_number(lap.get("distance")),
            )
        )
    return tuple(sorted(laps, key=lambda lap: lap.start_time))


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _stream_data(streams: Streams) -> dict[str, list[Any]]:
    if isinstance(streams, Mapping):
        items = [(key, stream) for key, stream in streams.items()]
    else:
        items = [(str(stream.get("type")), stream) for stream in streams]
    return {
        key: list(stream.get("data") or []) for key, stream in items if isinstance(stream, Mapping)
    }


def _at(values: list[Any] | None, index: int) -> Any:
    if values is None or index >= len(values):
        return None
    return values[index]


def _start(activity: Mapping[str, Any]) -> dt.datetime:
    value = activity.get("start_date")
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except ValueError as error:
        raise ActivityFileError(f"expected an ISO 8601 start_date, got {value!r}") from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def _sport(activity: Mapping[str, Any], has_positions: bool) -> Sport:
    name = str(activity.get("sport_type") or activity.get("type") or "")
    if name == "Run" and (activity.get("trainer") or not has_positions):
        return Sport.TREADMILL_RUNNING
    if name.endswith("Ride"):
        return Sport.CYCLING
    return STRAVA_SPORTS.get(name, Sport.OTHER)

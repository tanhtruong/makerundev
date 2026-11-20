import datetime as dt
import io
from typing import Any

import fitdecode

from makerundev.errors import ActivityFileError
from makerundev.model import Activity, Lap, Sport

SEMICIRCLE_TO_DEGREES = 180 / 2**31
MILLIMETRES_PER_METRE = 1000

FIT_SPORTS = {
    "running": Sport.RUNNING,
    "walking": Sport.WALKING,
    "hiking": Sport.HIKING,
    "cycling": Sport.CYCLING,
    "swimming": Sport.SWIMMING,
}
FIT_RUNNING_SUB_SPORTS = {"trail": Sport.TRAIL_RUNNING, "treadmill": Sport.TREADMILL_RUNNING}


def read_fit(data: bytes) -> Activity:
    rows: list[dict[str, Any]] = []
    sport = Sport.OTHER
    start_time: dt.datetime | None = None
    device: str | None = None
    laps: list[Lap] = []
    session_seen = False
    try:
        with fitdecode.FitReader(io.BytesIO(data), check_crc=fitdecode.CrcCheck.ENABLED) as reader:
            for frame in reader:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                if frame.name == "record":
                    rows.append(_record(frame))
                elif frame.name == "lap":
                    lap = _lap(frame)
                    if lap is not None:
                        laps.append(lap)
                elif frame.name == "session" and not session_seen:
                    session_seen = True
                    sport = _sport(_value(frame, "sport"), _value(frame, "sub_sport"))
                    start_time = _value(frame, "start_time")
                elif frame.name == "file_id" and device is None:
                    device = _device(frame)
    except fitdecode.FitError as error:
        raise ActivityFileError(f"unreadable FIT file: {error}") from error
    if sport.is_running:
        for row in rows:
            if row["cadence"] is not None:
                row["cadence"] *= 2
    return Activity.from_rows(
        rows, sport=sport, source_format="fit", device=device, start_time=start_time, laps=laps
    )


def _lap(frame: Any) -> Lap | None:
    start_time = _value(frame, "start_time")
    if not isinstance(start_time, dt.datetime):
        return None
    elapsed = _value(frame, "total_elapsed_time")
    distance = _value(frame, "total_distance")
    return Lap(
        start_time=start_time.astimezone(dt.UTC),
        elapsed_s=float(elapsed) if elapsed is not None else None,
        distance_m=float(distance) if distance is not None else None,
    )


def _value(frame: Any, name: str) -> Any:
    return frame.get_value(name, fallback=None)


def _record(frame: Any) -> dict[str, Any]:
    lat = _value(frame, "position_lat")
    lon = _value(frame, "position_long")
    cadence = _value(frame, "cadence")
    fractional = _value(frame, "fractional_cadence")
    if cadence is not None and fractional is not None:
        cadence += fractional
    step_length = _value(frame, "step_length")
    return {
        "timestamp": _value(frame, "timestamp"),
        "latitude": lat * SEMICIRCLE_TO_DEGREES if lat is not None else None,
        "longitude": lon * SEMICIRCLE_TO_DEGREES if lon is not None else None,
        "distance": _value(frame, "distance"),
        "speed": _first(frame, "enhanced_speed", "speed"),
        "altitude": _first(frame, "enhanced_altitude", "altitude"),
        "heart_rate": _value(frame, "heart_rate"),
        "cadence": cadence,
        "power": _value(frame, "power"),
        "temperature": _value(frame, "temperature"),
        "ground_contact_time": _value(frame, "stance_time"),
        "vertical_oscillation": _value(frame, "vertical_oscillation"),
        "step_length": step_length / MILLIMETRES_PER_METRE if step_length is not None else None,
    }


def _first(frame: Any, *names: str) -> Any:
    for name in names:
        value = _value(frame, name)
        if value is not None:
            return value
    return None


def _sport(sport: Any, sub_sport: Any) -> Sport:
    resolved = FIT_SPORTS.get(str(sport), Sport.OTHER)
    if resolved is Sport.RUNNING:
        return FIT_RUNNING_SUB_SPORTS.get(str(sub_sport), Sport.RUNNING)
    return resolved


def _device(frame: Any) -> str | None:
    manufacturer = _value(frame, "manufacturer")
    product = _first(frame, "garmin_product", "product_name", "product")
    parts = [str(part) for part in (manufacturer, product) if part is not None]
    return " ".join(parts) or None

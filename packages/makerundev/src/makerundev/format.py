import math
from collections.abc import Sequence
from enum import StrEnum

METRES_PER_MILE = 1609.344


class Unit(StrEnum):
    KM = "km"
    MI = "mi"

    @property
    def metres(self) -> float:
        return METRES_PER_MILE if self is Unit.MI else 1000.0


def duration(seconds: float) -> str:
    total = round(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def pace(seconds_per_km: float | None, unit: Unit = Unit.KM) -> str:
    if seconds_per_km is None:
        return "-"
    return f"{duration(seconds_per_km * (unit.metres / 1000))} /{unit}"


def distance(meters: float, unit: Unit = Unit.KM) -> str:
    return f"{meters / unit.metres:.2f} {unit}"


NAMED_DISTANCES_M = {21097.5: "Half marathon", 42195.0: "Marathon"}


def distance_name(meters: float) -> str:
    if meters in NAMED_DISTANCES_M:
        return NAMED_DISTANCES_M[meters]
    miles = round(meters / METRES_PER_MILE, 6)
    if miles >= 1 and miles.is_integer():
        return "1 mile" if miles == 1 else f"{miles:g} miles"
    if meters < 1000:
        return f"{meters:g} m"
    return f"{meters / 1000:g} km"


def zone_starts(boundaries_bpm: Sequence[float]) -> list[int]:
    return [math.ceil(boundary) for boundary in boundaries_bpm]


def zone_range(zone: int, boundaries_bpm: Sequence[float]) -> str:
    starts = zone_starts(boundaries_bpm)
    if zone == 0:
        return f"under {starts[0]} bpm"
    if zone == len(starts):
        return f"{starts[-1]} bpm and up"
    return f"{starts[zone - 1]}-{starts[zone] - 1} bpm"

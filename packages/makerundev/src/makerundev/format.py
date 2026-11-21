import math
from collections.abc import Sequence


def duration(seconds: float) -> str:
    total = round(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def pace(seconds_per_km: float | None) -> str:
    if seconds_per_km is None:
        return "-"
    return f"{duration(seconds_per_km)} /km"


def kilometres(meters: float) -> str:
    return f"{meters / 1000:.2f} km"


NAMED_DISTANCES_M = {1609.344: "1 mile", 21097.5: "Half marathon", 42195.0: "Marathon"}


def distance_name(meters: float) -> str:
    if meters in NAMED_DISTANCES_M:
        return NAMED_DISTANCES_M[meters]
    if meters < 1000:
        return f"{meters:g} m"
    return f"{meters / 1000:g} km"


def zone_range(zone: int, boundaries_bpm: Sequence[float]) -> str:
    starts = [math.ceil(boundary) for boundary in boundaries_bpm]
    if zone == 0:
        return f"under {starts[0]} bpm"
    if zone == len(starts):
        return f"{starts[-1]} bpm and up"
    return f"{starts[zone - 1]}-{starts[zone] - 1} bpm"

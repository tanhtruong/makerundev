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

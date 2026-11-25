from collections.abc import Sequence
from dataclasses import dataclass

from makerundev.metrics import (
    BANISTER_MALE,
    Summary,
    aerobic_decoupling,
    estimated_power,
    summarize,
    time_in_zones,
    trimp,
)
from makerundev.model import Activity


@dataclass(frozen=True, slots=True)
class ZoneTime:
    number: int
    seconds: float
    share: float


@dataclass(frozen=True, slots=True)
class Analysis:
    summary: Summary
    aerobic_decoupling_percent: float | None
    estimated_power_w: float | None
    zones: tuple[ZoneTime, ...] | None
    trimp: float | None


def analyse(
    activity: Activity,
    *,
    body_mass_kg: float | None = None,
    max_hr: float | None = None,
    resting_hr: float | None = None,
    zone_boundaries_bpm: Sequence[float] | None = None,
    trimp_coefficients: tuple[float, float] = BANISTER_MALE,
) -> Analysis:
    return Analysis(
        summary=summarize(activity),
        aerobic_decoupling_percent=aerobic_decoupling(activity),
        estimated_power_w=estimated_power(activity, body_mass_kg)
        if body_mass_kg is not None
        else None,
        zones=_zones(activity, zone_boundaries_bpm) if zone_boundaries_bpm else None,
        trimp=trimp(activity, resting_hr, max_hr, trimp_coefficients)
        if max_hr is not None and resting_hr is not None
        else None,
    )


def _zones(activity: Activity, boundaries_bpm: Sequence[float]) -> tuple[ZoneTime, ...] | None:
    seconds = time_in_zones(activity, boundaries_bpm)
    if seconds is None:
        return None
    total = sum(seconds)
    return tuple(
        ZoneTime(number=zone, seconds=time, share=time / total)
        for zone, time in enumerate(seconds, start=1)
    )

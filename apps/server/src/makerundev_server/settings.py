import functools
import os
import zoneinfo
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from makerundev.metrics import (
    BANISTER_FEMALE,
    BANISTER_MALE,
    BODY_MASS_RANGE_KG,
    DEFAULT_ZONE_THRESHOLDS,
)


class ZoneModel(StrEnum):
    MAX_HR_PERCENT = "max_hr_percent"
    HR_RESERVE_PERCENT = "hr_reserve_percent"


DEFAULT_ZONE_MODEL = ZoneModel.MAX_HR_PERCENT


class TrimpCoefficients(StrEnum):
    MALE = "male"
    FEMALE = "female"


COEFFICIENTS = {TrimpCoefficients.MALE: BANISTER_MALE, TrimpCoefficients.FEMALE: BANISTER_FEMALE}
ZONE_COUNT = 5
MAX_HR_RANGE = (100, 250)
RESTING_HR_RANGE = (20, 120)
ZONE_THRESHOLDS = "zone_thresholds_percent"
type Location = tuple[str] | tuple[str, int]
MAX_HR: Location = ("max_heart_rate_bpm",)
RESTING_HR: Location = ("resting_heart_rate_bpm",)
BODY_MASS: Location = ("body_mass_kg",)
TIMEZONE: Location = ("timezone",)


@functools.cache
def timezones() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


def default_timezone() -> str:
    candidates = [os.environ.get("TZ", "").removeprefix(":")]
    localtime = Path("/etc/localtime")
    if localtime.is_symlink():
        candidates.append(str(localtime.resolve()).partition("zoneinfo/")[2])
    return next((name for name in candidates if name in timezones()), "UTC")


@dataclass(frozen=True, slots=True)
class AthleteSettings:
    max_hr: int
    resting_hr: int
    trimp_coefficients: TrimpCoefficients = TrimpCoefficients.MALE
    timezone: str = "UTC"
    zone_model: ZoneModel = DEFAULT_ZONE_MODEL
    zone_thresholds: tuple[float, ...] = field(default=DEFAULT_ZONE_THRESHOLDS)
    body_mass_kg: float | None = None

    @property
    def coefficients(self) -> tuple[float, float]:
        return COEFFICIENTS[self.trimp_coefficients]

    def zone_boundaries_bpm(self) -> list[float]:
        floor, span = 0, self.max_hr
        if self.zone_model is ZoneModel.HR_RESERVE_PERCENT:
            floor, span = self.resting_hr, self.max_hr - self.resting_hr
        return [floor + span * threshold / 100 for threshold in self.zone_thresholds]

    def trimp_inputs(self) -> tuple[int, int, TrimpCoefficients]:
        return self.max_hr, self.resting_hr, self.trimp_coefficients


def rule_errors(
    max_hr: int,
    resting_hr: int,
    body_mass_kg: float | None,
    timezone: str,
    thresholds: Sequence[float],
) -> dict[Location, str]:
    errors: dict[Location, str] = {}
    for key, beats, (low, high) in (
        (MAX_HR, max_hr, MAX_HR_RANGE),
        (RESTING_HR, resting_hr, RESTING_HR_RANGE),
    ):
        if not low <= beats <= high:
            errors[key] = f"Enter a value from {low} to {high} bpm."
    if not errors and resting_hr >= max_hr:
        errors[RESTING_HR] = "Resting heart rate must be below max heart rate."

    if body_mass_kg is not None:
        low, high = BODY_MASS_RANGE_KG
        if not low <= body_mass_kg <= high:
            errors[BODY_MASS] = f"Enter a body mass from {low} to {high} kg."

    if timezone not in timezones():
        errors[TIMEZONE] = "Enter a timezone name such as Europe/Copenhagen."

    previous: float | None = None
    for index, threshold in enumerate(thresholds):
        if not 0 < threshold < 100:
            errors[(ZONE_THRESHOLDS, index)] = "Enter a percentage between 0 and 100."
            continue
        if previous is not None and threshold <= previous:
            errors[(ZONE_THRESHOLDS, index)] = "Each zone must start above the one before it."
        previous = threshold
    return errors

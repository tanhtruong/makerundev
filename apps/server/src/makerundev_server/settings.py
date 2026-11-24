import functools
import os
import zoneinfo
from collections.abc import Mapping, Sequence
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
ZONE_MODEL_LABELS: dict[str, str] = {
    ZoneModel.MAX_HR_PERCENT: "max heart rate",
    ZoneModel.HR_RESERVE_PERCENT: "heart-rate reserve",
}


class TrimpCoefficients(StrEnum):
    MALE = "male"
    FEMALE = "female"


COEFFICIENTS = {TrimpCoefficients.MALE: BANISTER_MALE, TrimpCoefficients.FEMALE: BANISTER_FEMALE}
ZONE_COUNT = 5
MAX_HR_RANGE = (100, 250)
RESTING_HR_RANGE = (20, 120)
ZONE_FIELDS = tuple(f"zone_{zone}" for zone in range(2, ZONE_COUNT + 1))
ZONE_THRESHOLDS = "zone_thresholds_percent"
type Location = tuple[str] | tuple[str, int]
MAX_HR: Location = ("max_heart_rate_bpm",)
RESTING_HR: Location = ("resting_heart_rate_bpm",)
BODY_MASS: Location = ("body_mass_kg",)
TIMEZONE: Location = ("timezone",)
FORM_NAMES: dict[Location, str] = {
    MAX_HR: "max_hr",
    RESTING_HR: "resting_hr",
    BODY_MASS: "body_mass_kg",
    TIMEZONE: "timezone",
    **{(ZONE_THRESHOLDS, index): name for index, name in enumerate(ZONE_FIELDS)},
}
FORM_FIELDS = (
    "max_hr",
    "resting_hr",
    "trimp_coefficients",
    "timezone",
    "zone_model",
    "body_mass_kg",
    *ZONE_FIELDS,
)


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


def form_values(settings: AthleteSettings | None) -> dict[str, str]:
    values = {
        "max_hr": str(settings.max_hr) if settings else "",
        "resting_hr": str(settings.resting_hr) if settings else "",
        "trimp_coefficients": settings.trimp_coefficients if settings else TrimpCoefficients.MALE,
        "timezone": settings.timezone if settings else default_timezone(),
        "zone_model": settings.zone_model if settings else DEFAULT_ZONE_MODEL,
        "body_mass_kg": _number(settings.body_mass_kg)
        if settings and settings.body_mass_kg is not None
        else "",
    }
    thresholds = settings.zone_thresholds if settings else DEFAULT_ZONE_THRESHOLDS
    values.update(zip(ZONE_FIELDS, map(_number, thresholds), strict=False))
    return values


def _number(value: float) -> str:
    return str(int(value)) if value.is_integer() else repr(value)


def rule_errors(
    max_hr: int | None,
    resting_hr: int | None,
    body_mass_kg: float | None,
    timezone: str,
    thresholds: Sequence[float | None],
) -> dict[Location, str]:
    errors: dict[Location, str] = {}
    for key, beats, (low, high) in (
        (MAX_HR, max_hr, MAX_HR_RANGE),
        (RESTING_HR, resting_hr, RESTING_HR_RANGE),
    ):
        if beats is not None and not low <= beats <= high:
            errors[key] = f"Enter a value from {low} to {high} bpm."
    if max_hr is not None and resting_hr is not None and not errors and resting_hr >= max_hr:
        errors[RESTING_HR] = "Resting heart rate must be below max heart rate."

    if body_mass_kg is not None:
        low, high = BODY_MASS_RANGE_KG
        if not low <= body_mass_kg <= high:
            errors[BODY_MASS] = f"Enter a body mass from {low} to {high} kg."

    if timezone not in timezones():
        errors[TIMEZONE] = "Enter a timezone name such as Europe/Copenhagen."

    previous: float | None = None
    for index, threshold in enumerate(thresholds):
        if threshold is None:
            continue
        if not 0 < threshold < 100:
            errors[(ZONE_THRESHOLDS, index)] = "Enter a percentage between 0 and 100."
            continue
        if previous is not None and threshold <= previous:
            errors[(ZONE_THRESHOLDS, index)] = "Each zone must start above the one before it."
        previous = threshold
    return errors


def parse_form(values: Mapping[str, str]) -> tuple[AthleteSettings | None, dict[str, str]]:
    errors: dict[str, str] = {}

    def whole(name: str) -> int | None:
        try:
            return int(values.get(name, "").strip())
        except ValueError:
            errors[name] = "Enter a whole number of beats per minute."
            return None

    max_hr = whole("max_hr")
    resting_hr = whole("resting_hr")

    try:
        coefficients = TrimpCoefficients(values.get("trimp_coefficients", ""))
    except ValueError:
        errors["trimp_coefficients"] = "Choose male or female coefficients."
        coefficients = TrimpCoefficients.MALE

    try:
        zone_model = ZoneModel(values.get("zone_model", ""))
    except ValueError:
        errors["zone_model"] = "Choose a zone model."
        zone_model = DEFAULT_ZONE_MODEL

    body_mass_kg: float | None = None
    if mass := values.get("body_mass_kg", "").strip():
        try:
            body_mass_kg = float(mass)
        except ValueError:
            errors["body_mass_kg"] = "Enter a body mass in kilograms."

    timezone = values.get("timezone", "").strip()

    thresholds: list[float | None] = []
    for name in ZONE_FIELDS:
        try:
            thresholds.append(float(values.get(name, "").strip()))
        except ValueError:
            errors[name] = "Enter a percentage."
            thresholds.append(None)

    rules = rule_errors(max_hr, resting_hr, body_mass_kg, timezone, thresholds)
    errors.update((FORM_NAMES[key], message) for key, message in rules.items())

    if errors or max_hr is None or resting_hr is None:
        return None, errors
    settings = AthleteSettings(
        max_hr=max_hr,
        resting_hr=resting_hr,
        trimp_coefficients=coefficients,
        timezone=timezone,
        zone_model=zone_model,
        zone_thresholds=tuple(threshold for threshold in thresholds if threshold is not None),
        body_mass_kg=body_mass_kg,
    )
    return settings, {}

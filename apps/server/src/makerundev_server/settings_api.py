from typing import Annotated

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError
from makerundev import format
from makerundev.metrics import DEFAULT_ZONE_THRESHOLDS
from pydantic import BaseModel, Field

from makerundev_server import settings as athlete
from makerundev_server.api import operation_id
from makerundev_server.settings import (
    DEFAULT_ZONE_MODEL,
    ZONE_COUNT,
    TrimpCoefficients,
    ZoneModel,
)
from makerundev_server.store import Store

Thresholds = Annotated[list[float], Field(min_length=ZONE_COUNT - 1, max_length=ZONE_COUNT - 1)]


class AthleteSettings(BaseModel):
    max_heart_rate_bpm: int
    resting_heart_rate_bpm: int
    trimp_coefficients: TrimpCoefficients
    zone_model: ZoneModel
    zone_thresholds_percent: Thresholds
    body_mass_kg: float | None
    timezone: str


class SettingsDefaults(BaseModel):
    trimp_coefficients: TrimpCoefficients
    zone_model: ZoneModel
    zone_thresholds_percent: Thresholds
    timezone: str


class SettingsSaved(BaseModel):
    settings: AthleteSettings
    zone_starts_bpm: list[int]
    trimp_recomputed: int
    trimp_unreadable: int


class SettingsView(BaseModel):
    settings: AthleteSettings | None
    defaults: SettingsDefaults
    zone_starts_bpm: list[int] | None
    highest_heart_rate_bpm: float | None
    timezones: list[str]


def router(store: Store) -> APIRouter:
    api = APIRouter(prefix="/api", generate_unique_id_function=operation_id)

    @api.get("/settings", tags=["settings"])
    def get_settings() -> SettingsView:
        saved = store.athlete_settings()
        return SettingsView(
            settings=_model(saved) if saved else None,
            defaults=SettingsDefaults(
                trimp_coefficients=TrimpCoefficients.MALE,
                zone_model=DEFAULT_ZONE_MODEL,
                zone_thresholds_percent=list(DEFAULT_ZONE_THRESHOLDS),
                timezone=athlete.default_timezone(),
            ),
            zone_starts_bpm=format.zone_starts(saved.zone_boundaries_bpm()) if saved else None,
            highest_heart_rate_bpm=store.highest_heart_rate(),
            timezones=sorted(athlete.timezones()),
        )

    @api.put("/settings", tags=["settings"])
    def save_settings(chosen: AthleteSettings) -> SettingsSaved:
        errors = athlete.rule_errors(
            chosen.max_heart_rate_bpm,
            chosen.resting_heart_rate_bpm,
            chosen.body_mass_kg,
            chosen.timezone,
            chosen.zone_thresholds_percent,
        )
        if errors:
            raise RequestValidationError(
                [
                    {"type": "value_error", "loc": ("body", *key), "msg": message}
                    for key, message in errors.items()
                ]
            )
        settings = _domain(chosen)
        result = store.save_athlete_settings(settings)
        return SettingsSaved(
            settings=chosen,
            zone_starts_bpm=format.zone_starts(settings.zone_boundaries_bpm()),
            trimp_recomputed=result.recomputed,
            trimp_unreadable=result.unreadable,
        )

    return api


def _model(saved: athlete.AthleteSettings) -> AthleteSettings:
    return AthleteSettings(
        max_heart_rate_bpm=saved.max_hr,
        resting_heart_rate_bpm=saved.resting_hr,
        trimp_coefficients=saved.trimp_coefficients,
        zone_model=saved.zone_model,
        zone_thresholds_percent=list(saved.zone_thresholds),
        body_mass_kg=saved.body_mass_kg,
        timezone=saved.timezone,
    )


def _domain(chosen: AthleteSettings) -> athlete.AthleteSettings:
    return athlete.AthleteSettings(
        max_hr=chosen.max_heart_rate_bpm,
        resting_hr=chosen.resting_heart_rate_bpm,
        trimp_coefficients=chosen.trimp_coefficients,
        timezone=chosen.timezone,
        zone_model=chosen.zone_model,
        zone_thresholds=tuple(chosen.zone_thresholds_percent),
        body_mass_kg=chosen.body_mass_kg,
    )

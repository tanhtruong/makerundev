import datetime as dt
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Dialect,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from makerundev_server.config import database_path


class UtcDateTime(TypeDecorator[dt.datetime]):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: dt.datetime | None, dialect: Dialect) -> dt.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetimes are not stored")
        return value.astimezone(dt.UTC).replace(tzinfo=None)

    def process_result_value(
        self, value: dt.datetime | None, dialect: Dialect
    ) -> dt.datetime | None:
        return value.replace(tzinfo=dt.UTC) if value is not None else None


NAME_LENGTH = 255


def activity_name(value: object) -> str | None:
    if value is None:
        return None
    return str(value).strip()[:NAME_LENGTH].strip() or None


class Base(DeclarativeBase):
    pass


class ActivityRow(Base):
    __tablename__ = "activities"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_activities_storage_key"),
        UniqueConstraint("external_source", "external_id", name="uq_activities_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sha256: Mapped[str | None] = mapped_column(String(64), unique=True)
    storage_key: Mapped[str] = mapped_column(String(64))
    external_source: Mapped[str | None] = mapped_column(String(16))
    external_id: Mapped[str | None] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(NAME_LENGTH))
    source_format: Mapped[str] = mapped_column(String(8))
    sport: Mapped[str] = mapped_column(String(32))
    device: Mapped[str | None] = mapped_column(String(128))
    start_time: Mapped[dt.datetime] = mapped_column(UtcDateTime, index=True)
    distance_m: Mapped[float] = mapped_column(Float)
    elapsed_s: Mapped[float] = mapped_column(Float)
    moving_s: Mapped[float] = mapped_column(Float)
    pace_s_per_km: Mapped[float | None] = mapped_column(Float)
    avg_heart_rate: Mapped[float | None] = mapped_column(Float)
    max_heart_rate: Mapped[float | None] = mapped_column(Float)
    elevation_gain_m: Mapped[float] = mapped_column(Float)
    trimp: Mapped[float | None] = mapped_column(Float)
    laps: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON(none_as_null=True))
    imported_at: Mapped[dt.datetime] = mapped_column(
        UtcDateTime, default=lambda: dt.datetime.now(dt.UTC)
    )


class AthleteSettingsRow(Base):
    __tablename__ = "athlete_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_athlete_settings_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    max_hr: Mapped[int] = mapped_column(Integer)
    resting_hr: Mapped[int] = mapped_column(Integer)
    trimp_coefficients: Mapped[str] = mapped_column(String(8))
    timezone: Mapped[str] = mapped_column(String(64))
    zone_model: Mapped[str] = mapped_column(String(32))
    zone_thresholds: Mapped[list[float]] = mapped_column(JSON)
    body_mass_kg: Mapped[float | None] = mapped_column(Float)


class SyncState:
    newest_synced: Mapped[dt.datetime | None] = mapped_column(UtcDateTime)
    backfill_before: Mapped[dt.datetime | None] = mapped_column(UtcDateTime)
    backfill_done: Mapped[bool] = mapped_column(Boolean, default=False)
    syncing: Mapped[bool] = mapped_column(Boolean, default=False)
    sync_message: Mapped[str | None] = mapped_column(String(255))
    last_sync_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime)
    imported: Mapped[int] = mapped_column(Integer, default=0)
    matched: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)


class StravaConnectionRow(SyncState, Base):
    __tablename__ = "strava_connection"
    __table_args__ = (CheckConstraint("id = 1", name="ck_strava_connection_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    oauth_state: Mapped[str | None] = mapped_column(String(64))
    access_token: Mapped[str | None] = mapped_column(String(255))
    refresh_token: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime)


class GarminConnectionRow(SyncState, Base):
    __tablename__ = "garmin_connection"
    __table_args__ = (CheckConstraint("id = 1", name="ck_garmin_connection_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    api_key: Mapped[str] = mapped_column(Text)
    token: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime)


MIGRATIONS = Path(__file__).parent / "migrations"
BASELINE_REVISION = "0001"


def connect(data_dir: Path) -> Engine:
    engine = create_engine(f"sqlite:///{database_path(data_dir)}")
    upgrade(engine)
    return engine


def upgrade(engine: Engine) -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = inspect(connection).get_table_names()
        if ActivityRow.__tablename__ in tables and "alembic_version" not in tables:
            command.stamp(config, BASELINE_REVISION)
        command.upgrade(config, "head")

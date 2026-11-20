import datetime as dt
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Dialect,
    Float,
    Integer,
    String,
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

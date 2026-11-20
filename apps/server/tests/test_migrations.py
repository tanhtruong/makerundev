import sqlite3

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.db import MIGRATIONS, Base, connect

SCHEMA_0_1_0 = """
CREATE TABLE activities (
    id INTEGER NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    source_format VARCHAR(8) NOT NULL,
    sport VARCHAR(32) NOT NULL,
    device VARCHAR(128),
    start_time DATETIME NOT NULL,
    distance_m FLOAT NOT NULL,
    elapsed_s FLOAT NOT NULL,
    moving_s FLOAT NOT NULL,
    pace_s_per_km FLOAT,
    avg_heart_rate FLOAT,
    max_heart_rate FLOAT,
    elevation_gain_m FLOAT NOT NULL,
    imported_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (sha256)
);
CREATE INDEX ix_activities_start_time ON activities (start_time);
INSERT INTO activities VALUES (
    1, 'ab', 'old.fit', 'fit', 'running', NULL, '2026-02-01 06:30:00.000000',
    5000.0, 1500.0, 1490.0, 298.0, 150.0, 170.0, 20.0, '2026-02-01 08:00:00.000000'
);
"""


def head_revision() -> str | None:
    return ScriptDirectory(str(MIGRATIONS)).get_current_head()


def assert_at_head_and_matches_models(engine) -> None:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"render_as_batch": True})
        assert context.get_current_revision() == head_revision()
        assert compare_metadata(context, Base.metadata) == []


def test_new_data_directory_is_created_at_head_and_matches_the_models(tmp_path):
    engine = connect(tmp_path)

    assert_at_head_and_matches_models(engine)


def test_database_from_before_migrations_upgrades_and_keeps_its_activities(tmp_path):
    with sqlite3.connect(tmp_path / "pacelab.db") as legacy:
        legacy.executescript(SCHEMA_0_1_0)

    client = TestClient(create_app(data_dir=tmp_path))

    activities = client.get("/api/activities").json()
    assert [(a["filename"], a["start_time"]) for a in activities] == [
        ("old.fit", "2026-02-01T06:30:00+00:00")
    ]
    assert_at_head_and_matches_models(connect(tmp_path))


def test_athlete_settings_hold_at_most_one_row(tmp_path):
    connect(tmp_path)
    insert = (
        "INSERT INTO athlete_settings VALUES "
        "(2, 190, 50, 'male', 'UTC', 'max_hr_percent', '[60, 70, 80, 90]')"
    )

    with sqlite3.connect(tmp_path / "makerundev.db") as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(insert)

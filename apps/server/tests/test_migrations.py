import datetime as dt
import sqlite3

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from makerundev.model import normalize_records
from makerundev_server import create_app
from makerundev_server.db import MIGRATIONS, Base, connect
from sqlalchemy import create_engine

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
    (tmp_path / "streams").mkdir()
    stream = normalize_records([{"timestamp": dt.datetime(2026, 2, 1, 6, 30, tzinfo=dt.UTC)}])
    stream.write_parquet(tmp_path / "streams" / "ab.parquet")

    client = TestClient(create_app(data_dir=tmp_path))

    activities = client.get("/api/activities").json()
    assert [(a["filename"], a["start_time"]) for a in activities] == [
        ("old.fit", "2026-02-01T06:30:00+00:00")
    ]
    assert_at_head_and_matches_models(connect(tmp_path))
    with sqlite3.connect(tmp_path / "pacelab.db") as db:
        identity = db.execute(
            "SELECT sha256, storage_key, external_source, external_id FROM activities"
        ).fetchall()
    assert identity == [("ab", "ab", None, None)]
    assert len(client.get(f"/api/activities/{activities[0]['id']}/records").json()) == 1
    assert client.get(f"/activities/{activities[0]['id']}").status_code == 200
    with sqlite3.connect(tmp_path / "pacelab.db") as db:
        assert db.execute("SELECT laps FROM activities").fetchall() == [("[]",)]
    duplicate = (
        "INSERT INTO activities (sha256, storage_key, filename, source_format, sport,"
        " start_time, distance_m, elapsed_s, moving_s, elevation_gain_m, imported_at)"
        " VALUES ('ab', 'other', 'again.fit', 'fit', 'running', '2026-02-02 06:30:00',"
        " 1.0, 1.0, 1.0, 0.0, '2026-02-02 08:00:00')"
    )
    with sqlite3.connect(tmp_path / "pacelab.db") as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(duplicate)


def test_strava_only_activities_get_the_strava_name_they_were_stored_under(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'makerundev.db'}")
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0006")
    insert = (
        "INSERT INTO activities (sha256, storage_key, external_source, external_id, filename,"
        " source_format, sport, start_time, distance_m, elapsed_s, moving_s, elevation_gain_m,"
        " imported_at) VALUES (?, ?, ?, ?, ?, 'fit', 'running', '2026-02-01 06:30:00',"
        " 1.0, 1.0, 1.0, 0.0, '2026-02-01 08:00:00')"
    )
    with sqlite3.connect(tmp_path / "makerundev.db") as db:
        db.execute(insert, (None, "strava-1", "strava", "1", "Lunch Run"))
        db.execute(insert, ("cd", "cd", "strava", "2", "watch.fit"))
        db.execute(insert, ("ef", "ef", None, None, "other.gpx"))
        db.execute(insert, (None, "strava-3", "strava", "3", "Strava activity"))
        db.execute(insert, (None, "strava-4", "strava", "4", " Hill reps\t"))
        db.execute(insert, (None, "strava-5", "strava", "5", "  "))

    connect(tmp_path)

    with sqlite3.connect(tmp_path / "makerundev.db") as db:
        names = db.execute("SELECT storage_key, name FROM activities ORDER BY id").fetchall()
    assert names == [
        ("strava-1", "Lunch Run"),
        ("cd", None),
        ("ef", None),
        ("strava-3", None),
        ("strava-4", "Hill reps"),
        ("strava-5", None),
    ]


def test_athlete_settings_hold_at_most_one_row(tmp_path):
    connect(tmp_path)
    insert = (
        "INSERT INTO athlete_settings VALUES "
        "(2, 190, 50, 'male', 'UTC', 'max_hr_percent', '[60, 70, 80, 90]')"
    )

    with sqlite3.connect(tmp_path / "makerundev.db") as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(insert)


def test_activities_without_a_file_are_told_apart_by_their_external_identity(tmp_path):
    connect(tmp_path)
    insert = (
        "INSERT INTO activities (storage_key, external_source, external_id, filename,"
        " source_format, sport, start_time, distance_m, elapsed_s, moving_s, elevation_gain_m,"
        " imported_at) VALUES (?, 'strava', ?, 'Run', 'strava', 'running',"
        " '2026-02-01 06:30:00', 1.0, 1.0, 1.0, 0.0, '2026-02-01 08:00:00')"
    )

    with sqlite3.connect(tmp_path / "makerundev.db") as db:
        db.execute(insert, ("strava-1", "1"))
        db.execute(insert, ("strava-2", "2"))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(insert, ("strava-3", "2"))

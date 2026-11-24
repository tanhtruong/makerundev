import math

import pytest
from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.db import ActivityRow, connect
from settings_payload import SETTINGS
from sqlalchemy import select
from sqlalchemy.orm import Session

RESERVE = (140 - 50) / (190 - 50)
STEADY_RUN_TRIMP = 1000 / 60 * RESERVE * 0.64 * math.exp(1.92 * RESERVE)


def stored_trimp(data_dir) -> list[float | None]:
    with Session(connect(data_dir)) as session:
        return list(session.scalars(select(ActivityRow.trimp).order_by(ActivityRow.id)))


def upload(client: TestClient, name: str, data: bytes) -> None:
    response = client.post(
        "/api/activities", files=[("files", (name, data, "application/octet-stream"))]
    )
    assert response.status_code == 200


def test_settings_are_read_and_saved_through_the_api(tmp_path, steady_run_fit, monkeypatch):
    monkeypatch.setenv("TZ", "America/Denver")
    client = TestClient(create_app(data_dir=tmp_path))
    upload(client, "run.fit", steady_run_fit)

    unset = client.get("/api/settings").json()

    assert unset["settings"] is None
    assert unset["zone_starts_bpm"] is None
    assert unset["defaults"] == {
        "trimp_coefficients": "male",
        "zone_model": "max_hr_percent",
        "zone_thresholds_percent": [60, 70, 80, 90],
        "timezone": "America/Denver",
    }
    assert unset["highest_heart_rate_bpm"] == 140
    assert {"Europe/Copenhagen", "UTC"} <= set(unset["timezones"])
    assert "Mars/Olympus" not in unset["timezones"]

    chosen = SETTINGS | {
        "zone_model": "hr_reserve_percent",
        "zone_thresholds_percent": [60, 72.5, 80, 90],
        "body_mass_kg": 68.5,
    }
    saved = client.put("/api/settings", json=chosen)

    assert saved.status_code == 200
    assert saved.json() == {
        "settings": chosen,
        "zone_starts_bpm": [134, 152, 162, 176],
        "trimp_recomputed": 1,
        "trimp_unreadable": 0,
    }
    assert stored_trimp(tmp_path) == [pytest.approx(STEADY_RUN_TRIMP)]
    reread = TestClient(create_app(data_dir=tmp_path)).get("/api/settings").json()
    assert reread["settings"] == chosen
    assert reread["zone_starts_bpm"] == [134, 152, 162, 176]


def refused(field: str | tuple[str, int], message: str) -> dict[str, object]:
    loc = ["body", *field] if isinstance(field, tuple) else ["body", field]
    return {"loc": loc, "msg": message, "type": "value_error"}


ZONES = "zone_thresholds_percent"
BEATS = "Enter a value from 100 to 250 bpm."
RESTING_BEATS = "Enter a value from 20 to 120 bpm."
PERCENT = "Enter a percentage between 0 and 100."
ASCENDING = "Each zone must start above the one before it."
TIMEZONE = "Enter a timezone name such as Europe/Copenhagen."
MASS = "Enter a body mass from 30 to 200 kg."


@pytest.mark.parametrize(
    ("changes", "errors"),
    [
        ({"max_heart_rate_bpm": 300}, [refused("max_heart_rate_bpm", BEATS)]),
        ({"resting_heart_rate_bpm": 190}, [refused("resting_heart_rate_bpm", RESTING_BEATS)]),
        (
            {"max_heart_rate_bpm": 110, "resting_heart_rate_bpm": 110},
            [refused("resting_heart_rate_bpm", "Resting heart rate must be below max heart rate.")],
        ),
        ({ZONES: [60, 70, 65, 90]}, [refused((ZONES, 2), ASCENDING)]),
        ({ZONES: [60, 70, 80, 100]}, [refused((ZONES, 3), PERCENT)]),
        ({ZONES: [60, 150, 80, 90]}, [refused((ZONES, 1), PERCENT)]),
        ({"timezone": "Mars/Olympus"}, [refused("timezone", TIMEZONE)]),
        ({"body_mass_kg": 29.9}, [refused("body_mass_kg", MASS)]),
        ({"body_mass_kg": 200.1}, [refused("body_mass_kg", MASS)]),
        (
            {"max_heart_rate_bpm": 300, "timezone": "Mars/Olympus"},
            [refused("max_heart_rate_bpm", BEATS), refused("timezone", TIMEZONE)],
        ),
    ],
)
def test_invalid_settings_are_refused_field_by_field_and_not_saved(tmp_path, changes, errors):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.put("/api/settings", json=SETTINGS | changes)

    assert response.status_code == 422
    assert response.json() == {"detail": errors}
    assert client.get("/api/settings").json()["settings"] is None


def test_a_zone_list_of_the_wrong_length_is_refused(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.put("/api/settings", json=SETTINGS | {ZONES: [60, 70, 80]})

    assert response.status_code == 422
    assert [error["loc"] for error in response.json()["detail"]] == [["body", ZONES]]


def save(client: TestClient, **changes: object) -> dict[str, object]:
    response = client.put("/api/settings", json=SETTINGS | changes)
    assert response.status_code == 200
    return response.json()


def test_trimp_is_recomputed_only_when_an_input_to_it_changes(tmp_path, steady_run_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    upload(client, "run.fit", steady_run_fit)
    save(client)

    unchanged = save(
        client, zone_thresholds_percent=[65, 70, 80, 90], timezone="UTC", body_mass_kg=70
    )
    assert (unchanged["trimp_recomputed"], unchanged["trimp_unreadable"]) == (0, 0)

    changed = save(client, trimp_coefficients="female")
    assert (changed["trimp_recomputed"], changed["trimp_unreadable"]) == (1, 0)
    assert stored_trimp(tmp_path) == [
        pytest.approx(1000 / 60 * RESERVE * 0.86 * math.exp(1.67 * RESERVE))
    ]


def test_a_null_body_mass_clears_the_saved_one(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    save(client, body_mass_kg=68.5)

    save(client, body_mass_kg=None)

    assert client.get("/api/settings").json()["settings"]["body_mass_kg"] is None


def test_activity_with_an_unreadable_stream_does_not_block_saving(tmp_path, steady_run_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    upload(client, "run.fit", steady_run_fit)
    save(client)
    assert stored_trimp(tmp_path) != [None]
    for stream in (tmp_path / "streams").iterdir():
        stream.unlink()

    saved = save(client, trimp_coefficients="female")

    assert (saved["trimp_recomputed"], saved["trimp_unreadable"]) == (0, 1)
    assert client.get("/api/settings").json()["settings"]["trimp_coefficients"] == "female"
    assert stored_trimp(tmp_path) == [None]

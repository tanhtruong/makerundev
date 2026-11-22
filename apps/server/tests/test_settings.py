import math

import pytest
from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.db import ActivityRow, connect
from sqlalchemy import select
from sqlalchemy.orm import Session

FORM = {
    "max_hr": "190",
    "resting_hr": "50",
    "trimp_coefficients": "male",
    "timezone": "Europe/Copenhagen",
    "zone_model": "max_hr_percent",
    "zone_2": "60",
    "zone_3": "70",
    "zone_4": "80",
    "zone_5": "90",
}

RESERVE = (140 - 50) / (190 - 50)
STEADY_RUN_TRIMP = 1000 / 60 * RESERVE * 0.64 * math.exp(1.92 * RESERVE)


def stored_trimp(data_dir) -> list[float | None]:
    with Session(connect(data_dir)) as session:
        return list(session.scalars(select(ActivityRow.trimp).order_by(ActivityRow.id)))


def upload(client: TestClient, name: str, data: bytes) -> None:
    response = client.post(
        "/activities", files=[("files", (name, data, "application/octet-stream"))]
    )
    assert response.status_code == 200


def save(client: TestClient, **changes: str):
    return client.post("/settings", data=FORM | changes, follow_redirects=False)


def test_settings_start_unset_with_default_zones_and_a_max_heart_rate_hint(
    tmp_path, steady_run_fit
):
    client = TestClient(create_app(data_dir=tmp_path))
    upload(client, "run.fit", steady_run_fit)

    page = client.get("/settings")

    assert page.status_code == 200
    assert 'name="max_hr" value=""' in page.text
    assert 'name="zone_2" value="60"' in page.text
    assert 'name="zone_5" value="90"' in page.text
    assert "Highest recorded in your activities: 140 bpm" in page.text


def test_saved_settings_persist_across_restarts(tmp_path):
    response = save(
        TestClient(create_app(data_dir=tmp_path)),
        zone_model="hr_reserve_percent",
        zone_3="72.1234567",
        body_mass_kg="68.5",
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/settings?recomputed=0&unreadable=0"

    page = TestClient(create_app(data_dir=tmp_path)).get("/settings")
    assert 'name="max_hr" value="190"' in page.text
    assert 'name="resting_hr" value="50"' in page.text
    assert 'name="zone_3" value="72.1234567"' in page.text
    assert 'name="body_mass_kg" value="68.5"' in page.text
    assert 'name="zone_2" value="60"' in page.text
    assert 'value="Europe/Copenhagen"' in page.text
    assert '<option value="male" selected>' in page.text
    assert '<option value="hr_reserve_percent" selected>' in page.text
    assert 'id="zone_2-note">134 bpm<' in page.text
    assert 'id="zone_3-note">151 bpm<' in page.text


def test_first_save_computes_trimp_for_activities_imported_before(tmp_path, steady_run_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    upload(client, "run.fit", steady_run_fit)
    assert stored_trimp(tmp_path) == [None]

    response = save(client)

    assert response.headers["location"] == "/settings?recomputed=1&unreadable=0"
    assert stored_trimp(tmp_path) == [pytest.approx(STEADY_RUN_TRIMP)]
    assert "TRIMP recomputed for 1 activity." in client.get(response.headers["location"]).text


def test_trimp_is_recomputed_only_when_an_input_to_it_changes(tmp_path, steady_run_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    upload(client, "run.fit", steady_run_fit)
    save(client)

    unchanged = save(client, zone_2="65", timezone="UTC", body_mass_kg="70")
    assert unchanged.headers["location"] == "/settings?recomputed=0&unreadable=0"

    changed = save(client, trimp_coefficients="female")
    assert changed.headers["location"] == "/settings?recomputed=1&unreadable=0"
    assert stored_trimp(tmp_path) == [
        pytest.approx(1000 / 60 * RESERVE * 0.86 * math.exp(1.67 * RESERVE))
    ]


def test_a_blank_body_mass_clears_the_saved_one(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    save(client, body_mass_kg="68.5")

    save(client, body_mass_kg="")

    assert 'name="body_mass_kg" value=""' in client.get("/settings").text


def test_activity_without_heart_rate_stores_no_trimp(tmp_path, make_fit):
    no_heart_rate = make_fit([{"t": float(i), "distance": i * 3.0} for i in range(301)])
    client = TestClient(create_app(data_dir=tmp_path))
    save(client)

    upload(client, "no-hr.fit", no_heart_rate)

    assert stored_trimp(tmp_path) == [None]


def test_activity_with_an_unreadable_stream_does_not_block_saving(tmp_path, steady_run_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    upload(client, "run.fit", steady_run_fit)
    for stream in (tmp_path / "streams").iterdir():
        stream.unlink()

    response = save(client)

    assert response.headers["location"] == "/settings?recomputed=0&unreadable=1"
    page = client.get(response.headers["location"]).text
    assert "Settings saved. 1 activity could not be read; see the server log." in page
    assert 'name="max_hr" value="190"' in page
    assert stored_trimp(tmp_path) == [None]


def test_a_malformed_notice_query_still_shows_the_form(tmp_path):
    page = TestClient(create_app(data_dir=tmp_path)).get("/settings?recomputed=x")

    assert page.status_code == 200
    assert "Settings saved." not in page.text


def test_an_out_of_range_zone_does_not_flag_the_next_one(tmp_path):
    response = save(TestClient(create_app(data_dir=tmp_path)), zone_3="150")

    assert response.status_code == 422
    assert response.text.count("Enter a percentage between 0 and 100.") == 1
    assert "Each zone must start above the one before it." not in response.text


@pytest.mark.parametrize(
    ("changes", "field", "message"),
    [
        ({"max_hr": "abc"}, "max_hr", "Enter a whole number of beats per minute."),
        ({"max_hr": "300"}, "max_hr", "Enter a value from 100 to 250 bpm."),
        ({"resting_hr": "190"}, "resting_hr", "Enter a value from 20 to 120 bpm."),
        ({"max_hr": "110", "resting_hr": "110"}, "resting_hr", "must be below max heart rate"),
        ({"zone_4": "65"}, "zone_4", "Each zone must start above the one before it."),
        ({"zone_5": "100"}, "zone_5", "Enter a percentage between 0 and 100."),
        ({"timezone": "Mars/Olympus"}, "timezone", "Enter a timezone name"),
        ({"trimp_coefficients": "other"}, "trimp_coefficients", "Choose male or female"),
        ({"zone_model": "other"}, "zone_model", "Choose a zone model."),
        ({"body_mass_kg": "29.9"}, "body_mass_kg", "Enter a body mass from 30 to 200 kg."),
        ({"body_mass_kg": "200.1"}, "body_mass_kg", "Enter a body mass from 30 to 200 kg."),
        ({"body_mass_kg": "heavy"}, "body_mass_kg", "Enter a body mass in kilograms."),
    ],
)
def test_invalid_settings_are_shown_back_and_not_saved(tmp_path, changes, field, message):
    client = TestClient(create_app(data_dir=tmp_path))

    response = save(client, **changes)

    assert response.status_code == 422
    assert message in response.text
    assert "Nothing was saved." in response.text
    for name, value in changes.items():
        if name not in ("trimp_coefficients", "zone_model"):
            assert f'name="{name}" value="{value}"' in response.text
    assert 'name="max_hr" value=""' in client.get("/settings").text

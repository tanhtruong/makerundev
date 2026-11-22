import pytest
from fastapi.testclient import TestClient
from makerundev_server import create_app

FORM = {
    "max_hr": "190",
    "resting_hr": "50",
    "trimp_coefficients": "male",
    "timezone": "UTC",
    "zone_model": "max_hr_percent",
    "zone_2": "60",
    "zone_3": "70",
    "zone_4": "80",
    "zone_5": "90",
}
SAVED = 'name="max_hr" value="190"'


@pytest.mark.parametrize(
    "headers",
    [
        {"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"},
        {"Sec-Fetch-Site": "same-site", "Origin": "http://testserver:5173"},
        {"Origin": "https://evil.example"},
        {"Origin": "http://testserver:5173"},
        {"Origin": "http://testserver.evil.example"},
        {"Origin": "null", "Host": ""},
    ],
)
def test_a_cross_site_post_is_refused_and_changes_nothing(tmp_path, headers):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.post("/settings", data=FORM, headers=headers, follow_redirects=False)

    assert response.status_code == 403
    page = client.get("/settings", headers=headers)
    assert page.status_code == 200
    assert SAVED not in page.text


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Sec-Fetch-Site": "same-origin", "Origin": "https://run.example.com"},
        {"Sec-Fetch-Site": "none"},
        {"Origin": "https://testserver"},
    ],
)
def test_a_same_origin_or_header_less_post_goes_through(tmp_path, headers):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.post("/settings", data=FORM, headers=headers, follow_redirects=False)

    assert response.status_code == 303
    assert SAVED in client.get("/settings").text

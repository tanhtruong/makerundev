import datetime as dt
from pathlib import Path

import openapi
import pytest
from fastapi.testclient import TestClient
from makerundev_server import create_app

ROWS = [{"t": float(i), "distance": i * 3.0, "hr": 140} for i in range(301)]


def at(day: int) -> dt.datetime:
    return dt.datetime(2026, 3, day, 7, 0, tzinfo=dt.UTC)


@pytest.fixture
def client(tmp_path, make_fit):
    client = TestClient(create_app(data_dir=tmp_path))
    uploads = [
        ("mon.fit", at(2), ROWS),
        ("tie-a.fit", at(4), ROWS),
        ("tie-b.fit", at(4), ROWS[:200]),
        ("tue.fit", at(3), ROWS),
        ("sun.fit", at(1), ROWS),
    ]
    for filename, start, rows in uploads:
        fit = make_fit(rows, start=start)
        response = client.post("/activities", files=[("files", (filename, fit))])
        assert response.status_code == 200
    return client


def test_activities_are_paged_newest_first_with_the_total(client):
    pages = [
        client.get("/api/activities", params={"limit": 2, "offset": offset}).json()
        for offset in (0, 2, 4)
    ]

    assert [[a["filename"] for a in page["items"]] for page in pages] == [
        ["tie-b.fit", "tie-a.fit"],
        ["tue.fit", "mon.fit"],
        ["sun.fit"],
    ]
    assert [page["total"] for page in pages] == [5, 5, 5]
    first = client.get("/api/activities").json()["items"][0]
    assert (first["start_time"], first["avg_heart_rate_bpm"]) == ("2026-03-04T07:00:00Z", 140.0)


@pytest.mark.parametrize("params", [{"limit": 201}, {"limit": 0}, {"offset": -1}])
def test_a_page_outside_the_limits_is_refused(client, params):
    response = client.get("/api/activities", params=params)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", next(iter(params))]


def test_the_committed_openapi_schema_matches_the_app():
    committed = Path(openapi.SCHEMA).read_text()

    assert committed == openapi.render(), "apps/server/openapi.json is stale: run make openapi"

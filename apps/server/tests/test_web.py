import pytest
from fastapi.testclient import TestClient
from makerundev_server import create_app

INDEX = "<!doctype html><title>makerundev</title><div id=root></div>"


@pytest.fixture
def built(tmp_path):
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text(INDEX)
    (web / "assets" / "app-1a2b.js").write_text("console.log(1)")
    return TestClient(create_app(data_dir=tmp_path / "data", web_dir=web))


def test_the_built_app_answers_every_path_the_server_does_not_own(built):
    for path in ("/", "/activities", "/activities/1", "/import", "/training-load/2026?x=1"):
        response = built.get(path)
        assert (response.status_code, response.text) == (200, INDEX), path
    assert built.get("/assets/app-1a2b.js").text == "console.log(1)"
    assert built.get("/assets/missing.js").status_code == 404
    assert built.get("/api/nope").json() == {"detail": "not found"}


def test_without_a_build_the_app_says_how_to_build_it(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path, web_dir=tmp_path / "web"))

    response = client.get("/")

    assert response.status_code == 503
    assert "make build-web" in response.text
    assert client.get("/api/activities").json() == {"items": [], "total": 0}


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ("/load/", "/load"),
        ("/api/activities/?limit=2", "/api/activities?limit=2"),
        ("/activities/", "/activities"),
    ],
)
def test_a_trailing_slash_redirects_to_the_path_without_it(built, path, target):
    response = built.get(path, follow_redirects=False)

    assert (response.status_code, response.headers["location"]) == (307, target)

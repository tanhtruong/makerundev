import os

import pytest
from fastapi.testclient import TestClient
from makerundev_server import create_app
from pmtiles_file import pmtiles_bytes, write_pmtiles

RASTER = "https://tiles.example.com/{z}/{x}/{y}.png?key=secret"
STYLE = "https://api.example.com/maps/streets/style.json?key=secret"
LONG_URL = "https://tiles.example.com/" + "a" * 1980 + "/{z}/{x}/{y}"

SCHEME = "Use an https:// address, or http:// only for an address on your own network."
NOT_A_URL = "That is not a web address."
NO_HOST = "The address needs a host name."
TOO_LONG = "Keep the address to 2,000 characters or fewer."
USERINFO = "Leave the user name and password out of the address."
FRAGMENT = "Remove the # and what follows it from the address."
RASTER_PLACEHOLDERS = "A raster tile address needs {z}, {x} and {y}."
STYLE_PLACEHOLDERS = "A style address points to one style file, without {z}, {x} or {y}."
URL_MISSING = "Paste the address of the tiles or the style."
PRESET_URL = "OpenStreetMap and OpenFreeMap come with their own address."
ATTRIBUTION_MISSING = "Write who the map data and tiles are from, as the provider asks."
ATTRIBUTION_TOO_LONG = "Keep the attribution to 200 characters or fewer."
ATTRIBUTION_MARKUP = "Write the attribution as plain text, without HTML."
PRESET_ATTRIBUTION = "OpenStreetMap and OpenFreeMap come with their own attribution."
FILE_URL = "A local tile file comes with its own address."
FILE_ATTRIBUTION = "A local tile file comes with its own attribution."
FILE_UNLISTED = "Pick a .pmtiles file from the data directory."
FILE_NOT_TAKEN = "Only a local tile file takes a file name."

OPENSTREETMAP = {
    "kind": "openstreetmap",
    "rendering": "raster",
    "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "dark_url": None,
    "attribution": "© OpenStreetMap contributors",
    "provider": "OpenStreetMap",
    "terms_url": "https://operations.osmfoundation.org/policies/tiles/",
    "privacy_url": "https://wiki.osmfoundation.org/wiki/Privacy_Policy",
    "file": None,
    "file_missing": False,
}
OPENFREEMAP = {
    "kind": "openfreemap",
    "rendering": "style",
    "url": "https://tiles.openfreemap.org/styles/liberty",
    "dark_url": "https://tiles.openfreemap.org/styles/dark",
    "attribution": "OpenFreeMap © OpenMapTiles Data from OpenStreetMap",
    "provider": "OpenFreeMap",
    "terms_url": "https://openfreemap.org/tos/",
    "privacy_url": "https://openfreemap.org/privacy/",
    "file": None,
    "file_missing": False,
}


def put(client, kind, url=None, attribution=None):
    body = {"kind": kind, "url": url, "attribution": attribution}
    return client.put("/api/map-source", json=body)


def local(file):
    return {"kind": "pmtiles", "url": None, "attribution": None, "file": file}


def custom_raster(url):
    return {"kind": "custom_raster", "url": url, "attribution": "© Example Maps"}


def test_a_map_source_is_saved_read_and_removed_with_presets_resolved_by_the_server(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    assert client.get("/api/map-source").json() == {
        "source": None,
        "presets": [OPENSTREETMAP, OPENFREEMAP],
        "files": [],
    }

    saved = put(client, "custom_raster", RASTER, "  © Example Maps  ")

    custom = {
        "kind": "custom_raster",
        "rendering": "raster",
        "url": RASTER,
        "dark_url": None,
        "attribution": "© Example Maps",
        "provider": "tiles.example.com",
        "terms_url": None,
        "privacy_url": None,
        "file": None,
        "file_missing": False,
    }
    assert (saved.status_code, saved.json()["source"]) == (200, custom)
    restarted = TestClient(create_app(data_dir=tmp_path)).get("/api/map-source")
    assert restarted.headers.get("cache-control") == "no-store"
    assert restarted.json()["source"] == custom

    style = put(client, "custom_style", STYLE, "© Example").json()["source"]
    assert (style["rendering"], style["url"], style["provider"]) == (
        "style",
        STYLE,
        "api.example.com",
    )

    put(client, "openstreetmap")
    assert client.get("/api/map-source").json()["source"] == OPENSTREETMAP

    put(client, "openfreemap")
    assert client.get("/api/map-source").json()["source"] == OPENFREEMAP

    removed = client.delete("/api/map-source")
    assert (removed.status_code, removed.json()["source"]) == (200, None)
    assert TestClient(create_app(data_dir=tmp_path)).get("/api/map-source").json()["source"] is None


@pytest.mark.parametrize(
    ("body", "field", "message"),
    [
        (custom_raster("http://tiles.example.com/{z}/{x}/{y}.png"), "url", SCHEME),
        (custom_raster("http://8.8.8.8/{z}/{x}/{y}.png"), "url", SCHEME),
        (custom_raster("http://172.32.0.1/{z}/{x}/{y}.png"), "url", SCHEME),
        (custom_raster("http://[2001:db8::1]/{z}/{x}/{y}.png"), "url", SCHEME),
        (custom_raster("http://tiles.localhost.example.com/{z}/{x}/{y}.png"), "url", SCHEME),
        (custom_raster("ftp://tiles.example.com/{z}/{x}/{y}.png"), "url", SCHEME),
        (custom_raster("tiles.example.com/{z}/{x}/{y}.png"), "url", SCHEME),
        (custom_raster("https://tiles.example.com:99999/{z}/{x}/{y}.png"), "url", NOT_A_URL),
        (custom_raster("https:///{z}/{x}/{y}.png"), "url", NO_HOST),
        (
            custom_raster(f"https://tiles.example.com/{'a' * 1980}/{{z}}/{{x}}/{{y}}"),
            "url",
            TOO_LONG,
        ),
        (custom_raster("https://me:pw@tiles.example.com/{z}/{x}/{y}.png"), "url", USERINFO),
        (custom_raster("https://tiles.example.com/{z}/{x}/{y}.png#top"), "url", FRAGMENT),
        (custom_raster("https://tiles.example.com/{z}/{x}.png"), "url", RASTER_PLACEHOLDERS),
        (custom_raster(None), "url", URL_MISSING),
        (
            {"kind": "custom_style", "url": "https://tiles.example.com/{z}/style.json"}
            | {"attribution": "© Example"},
            "url",
            STYLE_PLACEHOLDERS,
        ),
        (
            {"kind": "openstreetmap", "url": "https://tiles.example.com/{z}/{x}/{y}.png"}
            | {"attribution": None},
            "url",
            PRESET_URL,
        ),
        (
            {"kind": "openfreemap", "url": None, "attribution": "© Someone else"},
            "attribution",
            PRESET_ATTRIBUTION,
        ),
        (custom_raster(RASTER) | {"attribution": None}, "attribution", ATTRIBUTION_MISSING),
        (custom_raster(RASTER) | {"attribution": "   "}, "attribution", ATTRIBUTION_MISSING),
        (custom_raster(RASTER) | {"attribution": "©" * 201}, "attribution", ATTRIBUTION_TOO_LONG),
        (
            custom_raster(RASTER) | {"attribution": "<b>Example</b>"},
            "attribution",
            ATTRIBUTION_MARKUP,
        ),
        (local("berlin.pmtiles") | {"kind": "openstreetmap"}, "file", FILE_NOT_TAKEN),
        (local("berlin.pmtiles") | {"url": RASTER}, "url", FILE_URL),
        (local("berlin.pmtiles") | {"attribution": "© Me"}, "attribution", FILE_ATTRIBUTION),
    ],
)
def test_a_refused_map_source_answers_422_on_its_field_and_is_not_saved(
    tmp_path, body, field, message
):
    write_pmtiles(tmp_path / "berlin.pmtiles")
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.put("/api/map-source", json=body)

    assert response.status_code == 422
    assert [(e["loc"], e["msg"]) for e in response.json()["detail"]] == [(["body", field], message)]
    assert client.get("/api/map-source").json()["source"] is None


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.5:8080/{z}/{x}/{y}.png",
        "http://172.20.0.1/{z}/{x}/{y}.png",
        "http://192.168.1.10/{z}/{x}/{y}.png",
        "http://127.0.0.1/{z}/{x}/{y}.png",
        "http://169.254.10.1/{z}/{x}/{y}.png",
        "http://[::1]:8080/{z}/{x}/{y}.png",
        "http://[fe80::1]/{z}/{x}/{y}.png",
        "http://[fd12:3456::1]/{z}/{x}/{y}.png",
        "http://localhost:8080/{z}/{x}/{y}.png",
        "http://TILES.Local./{z}/{x}/{y}.png",
        "http://nas.lan/{z}/{x}/{y}.png",
        "http://box.home.arpa/{z}/{x}/{y}.png",
        "http://tiles.internal/{z}/{x}/{y}.png",
        "http://tileserver/{z}/{x}/{y}.png",
        "https://tiles.example.com/{z}/{x}/{y}@2x.png?key=abc&lang=en",
    ],
)
def test_a_private_http_or_any_https_raster_url_is_saved(tmp_path, url):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.put("/api/map-source", json=custom_raster(url))

    assert response.status_code == 200
    assert client.get("/api/map-source").json()["source"]["url"] == url


def test_a_tile_file_in_the_data_directory_is_listed_saved_and_served_with_range_requests(
    tmp_path,
):
    data = write_pmtiles(tmp_path / "Berlin Mitte.pmtiles")
    (tmp_path / "Copenhagen.PMTILES").write_bytes(pmtiles_bytes())
    elsewhere = tmp_path.parent / f"{tmp_path.name}-elsewhere"
    elsewhere.mkdir()
    write_pmtiles(elsewhere / "linked.pmtiles")
    os.symlink(elsewhere / "linked.pmtiles", tmp_path / "linked.pmtiles")
    (tmp_path / "notes.txt").write_text("not a tile file")
    (tmp_path / "extracts").mkdir()
    write_pmtiles(tmp_path / "extracts" / "nested.pmtiles")
    (tmp_path / "folder.pmtiles").mkdir()
    client = TestClient(create_app(data_dir=tmp_path))

    files = client.get("/api/map-source").json()["files"]

    assert files == [
        {"name": "Berlin Mitte.pmtiles", "size_bytes": len(data)},
        {"name": "Copenhagen.PMTILES", "size_bytes": len(data)},
        {"name": "linked.pmtiles", "size_bytes": len(data)},
    ]

    saved = client.put("/api/map-source", json=local("Berlin Mitte.pmtiles"))

    served = {
        "kind": "pmtiles",
        "rendering": "pmtiles",
        "url": "/tiles/Berlin%20Mitte.pmtiles",
        "dark_url": None,
        "attribution": "© OpenStreetMap contributors",
        "provider": "this instance",
        "terms_url": None,
        "privacy_url": None,
        "file": "Berlin Mitte.pmtiles",
        "file_missing": False,
    }
    assert (saved.status_code, saved.json()["source"]) == (200, served)
    restarted = TestClient(create_app(data_dir=tmp_path))
    assert restarted.get("/api/map-source").json()["source"] == served

    header = restarted.get(served["url"], headers={"Range": "bytes=0-126"})
    assert (header.status_code, header.content) == (206, data[:127])
    assert header.headers["content-range"] == f"bytes 0-126/{len(data)}"
    assert header.headers["cache-control"] == "no-cache"
    whole = restarted.get("/tiles/linked.pmtiles")
    assert (whole.status_code, whole.content) == (200, pmtiles_bytes())


@pytest.mark.parametrize(
    "name",
    [
        "berlin.pmtiles",
        "makerundev.db",
        "notes.txt",
        "../outside.pmtiles",
        "extracts/nested.pmtiles",
        "/etc/outside.pmtiles",
        "",
        "COPENHAGEN.pmtiles",
    ],
)
def test_a_tile_file_name_not_in_the_listing_is_refused_and_not_served(tmp_path, name):
    write_pmtiles(tmp_path / "Copenhagen.pmtiles")
    write_pmtiles(tmp_path.parent / "outside.pmtiles")
    (tmp_path / "notes.txt").write_text("not a tile file")
    (tmp_path / "extracts").mkdir()
    write_pmtiles(tmp_path / "extracts" / "nested.pmtiles")
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.put("/api/map-source", json=local(name))

    assert response.status_code == 422
    assert [(e["loc"], e["msg"]) for e in response.json()["detail"]] == [
        (["body", "file"], FILE_UNLISTED)
    ]
    assert client.get("/api/map-source").json()["source"] is None
    served = client.get("/tiles/" + name.replace("/", "%2F").replace(".", "%2E"))
    assert served.status_code == 404


def test_a_saved_tile_file_that_left_the_data_directory_stays_chosen_and_is_reported_missing(
    tmp_path,
):
    write_pmtiles(tmp_path / "copenhagen.pmtiles")
    client = TestClient(create_app(data_dir=tmp_path))
    client.put("/api/map-source", json=local("copenhagen.pmtiles"))

    (tmp_path / "copenhagen.pmtiles").unlink()

    view = client.get("/api/map-source").json()
    assert (view["files"], view["source"]["file"], view["source"]["file_missing"]) == (
        [],
        "copenhagen.pmtiles",
        True,
    )
    assert client.get("/tiles/copenhagen.pmtiles").status_code == 404

import pytest


@pytest.fixture(autouse=True)
def strava_application(monkeypatch):
    monkeypatch.setenv("MAKERUNDEV_STRAVA_CLIENT_ID", "4242")
    monkeypatch.setenv("MAKERUNDEV_STRAVA_CLIENT_SECRET", "application-secret")

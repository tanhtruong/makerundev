import base64
import binascii
import datetime as dt
import email.utils
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx2

API_URL = "https://personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
SEARCH_PATH = "/activitylist-service/activities/search/activities"
DOWNLOAD_PATH = "/download-service/files/activity/{}"
ACTIVITY_URL = "https://connect.garmin.com/modern/activity/{}"
PAGE_SIZE = 99
PAUSE_S = 1.0
TOKEN_LIFETIME = dt.timedelta(hours=24)


class GarminError(Exception):
    pass


class RateLimited(GarminError):
    def __init__(self, retry_after: str | None) -> None:
        super().__init__("Garmin asked to slow down")
        self.retry_after = retry_after


class Unauthorized(GarminError):
    pass


class Refused(GarminError):
    def __init__(self, status: int) -> None:
        super().__init__(f"Garmin answered {status}")


@dataclass(frozen=True, slots=True)
class Token:
    value: str
    expires_at: dt.datetime


class GarminClient:
    def __init__(
        self,
        transport: httpx2.BaseTransport | None = None,
        pause: float = PAUSE_S,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.http = httpx2.Client(transport=transport, timeout=60.0)
        self.pause = pause
        self.sleep = sleep
        self.last_request: float | None = None

    def token(self, key: str) -> Token:
        response = self._send("POST", TOKEN_PATH, f"ApiKey {key}")
        if 400 <= response.status_code < 500:
            raise Unauthorized("Garmin did not accept the key")
        response.raise_for_status()
        value = response.text.strip()
        if not value:
            raise GarminError("Garmin returned an empty token")
        return Token(value, _expiry(value))

    def activities(
        self,
        token: str,
        start: int = 0,
        since: dt.date | None = None,
        until: dt.date | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, int | str] = {"start": start, "limit": PAGE_SIZE}
        if since is not None:
            params["startDate"] = since.isoformat()
        if until is not None:
            params["endDate"] = until.isoformat()
        response = self._send("GET", SEARCH_PATH, f"Bearer {token}", params)
        response.raise_for_status()
        listed = response.json()
        if not isinstance(listed, list):
            raise GarminError("Garmin's activity list was not a list")
        return [entry for entry in listed if isinstance(entry, dict)]

    def download(self, token: str, activity_id: str) -> bytes:
        response = self._send("GET", DOWNLOAD_PATH.format(activity_id), f"Bearer {token}")
        if 400 <= response.status_code < 500:
            raise Refused(response.status_code)
        response.raise_for_status()
        if not response.content:
            raise Refused(response.status_code)
        return response.content

    def _send(
        self,
        method: str,
        path: str,
        authorization: str,
        params: dict[str, int | str] | None = None,
    ) -> httpx2.Response:
        if self.last_request is not None:
            wait = self.pause - (time.monotonic() - self.last_request)
            if wait > 0:
                self.sleep(wait)
        try:
            response = self.http.request(
                method,
                API_URL + path,
                params=params,
                headers={"Accept": "*/*", "Authorization": authorization},
            )
        finally:
            self.last_request = time.monotonic()
        if response.status_code == 429:
            raise RateLimited(response.headers.get("Retry-After"))
        if response.status_code == 401 and path != TOKEN_PATH:
            raise Unauthorized("Garmin rejected the access token")
        return response


def _expiry(token: str) -> dt.datetime:
    fallback = dt.datetime.now(dt.UTC) + TOKEN_LIFETIME
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return dt.datetime.fromtimestamp(int(claims["exp"]), dt.UTC)
    except (IndexError, KeyError, TypeError, ValueError, binascii.Error, OverflowError):
        return fallback


def retry_at(retry_after: str | None, now: dt.datetime) -> dt.datetime | None:
    text = (retry_after or "").strip()
    try:
        if text.isdigit():
            return now + dt.timedelta(seconds=int(text))
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        return None
    if when.tzinfo is None:
        return when.replace(tzinfo=dt.UTC)
    return when.astimezone(dt.UTC)

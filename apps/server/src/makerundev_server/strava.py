import datetime as dt
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx2
from makerundev.io.strava import STREAM_KEYS

from makerundev_server import config
from makerundev_server.sync_errors import RateLimited, Refused, Unauthorized

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
REVOKE_URL = "https://www.strava.com/oauth/revoke"
API_URL = "https://www.strava.com/api/v3"
ACTIVITY_URL = "https://www.strava.com/activities/{}"
SCOPE = "activity:read_all"
PAGE_SIZE = 100
SHORT_RESERVE = 5
DAILY_RESERVE = 20


@dataclass(frozen=True, slots=True)
class Credentials:
    client_id: str
    client_secret: str


@dataclass(frozen=True, slots=True)
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: dt.datetime


def credentials() -> Credentials | None:
    client_id = config.env("STRAVA_CLIENT_ID", "").strip()
    client_secret = config.env("STRAVA_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    return Credentials(client_id, client_secret)


class StravaClient:
    def __init__(
        self, credentials: Credentials, transport: httpx2.BaseTransport | None = None
    ) -> None:
        self.credentials = credentials
        self.http = httpx2.Client(transport=transport, timeout=30.0)
        self.remaining: tuple[int, int] | None = None

    def authorize_url(self, redirect_uri: str, state: str) -> str:
        query = {
            "client_id": self.credentials.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": SCOPE,
            "state": state,
        }
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    def exchange(self, code: str) -> Tokens:
        return self._token({"grant_type": "authorization_code", "code": code})

    def refresh(self, refresh_token: str) -> Tokens:
        return self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})

    def revoke(self, access_token: str) -> None:
        auth = httpx2.BasicAuth(self.credentials.client_id, self.credentials.client_secret)
        response = self.http.post(REVOKE_URL, data={"token": access_token}, auth=auth)
        response.raise_for_status()

    def activities(
        self,
        access_token: str,
        before: dt.datetime | None = None,
        after: dt.datetime | None = None,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        params: dict[str, int] = {"page": page, "per_page": PAGE_SIZE}
        if before is not None:
            params["before"] = int(before.timestamp())
        if after is not None:
            params["after"] = int(after.timestamp())
        response = self._get(access_token, "/athlete/activities", params)
        response.raise_for_status()
        listed: list[dict[str, Any]] = response.json()
        return listed

    def activity(self, access_token: str, activity_id: str) -> dict[str, Any] | None:
        return self._found(self._get(access_token, f"/activities/{activity_id}", {}))

    def streams(self, access_token: str, activity_id: str) -> dict[str, Any] | None:
        params = {"keys": ",".join(STREAM_KEYS), "key_by_type": "true"}
        return self._found(self._get(access_token, f"/activities/{activity_id}/streams", params))

    def _found(self, response: httpx2.Response) -> dict[str, Any] | None:
        if response.status_code == 404:
            return None
        if 400 <= response.status_code < 500:
            raise Refused(f"Strava answered {response.status_code}")
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        return body

    def _token(self, grant: dict[str, str]) -> Tokens:
        data = {
            "client_id": self.credentials.client_id,
            "client_secret": self.credentials.client_secret,
        } | grant
        response = self.http.post(TOKEN_URL, data=data)
        if response.status_code in (400, 401):
            raise Unauthorized("Strava did not accept the authorisation")
        response.raise_for_status()
        body = response.json()
        return Tokens(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            expires_at=dt.datetime.fromtimestamp(body["expires_at"], dt.UTC),
        )

    def ensure(self, requests: int) -> None:
        if self.remaining is None:
            return
        short, daily = (left - (requests - 1) for left in self.remaining)
        if daily < DAILY_RESERVE:
            raise RateLimited("paused_daily")
        if short < SHORT_RESERVE:
            raise RateLimited("paused_short")

    def _get(self, access_token: str, path: str, params: dict[str, Any]) -> httpx2.Response:
        self.ensure(1)
        response = self.http.get(
            API_URL + path, params=params, headers={"Authorization": f"Bearer {access_token}"}
        )
        self.remaining = _remaining(response.headers) or self.remaining
        if response.status_code == 429:
            daily = self.remaining is not None and self.remaining[1] <= 0
            raise RateLimited("paused_daily" if daily else "paused_short")
        if response.status_code == 401:
            raise Unauthorized("Strava rejected the access token")
        return response


def _remaining(headers: httpx2.Headers) -> tuple[int, int] | None:
    for prefix in ("X-ReadRateLimit", "X-RateLimit"):
        limit = _pair(headers.get(f"{prefix}-Limit"))
        usage = _pair(headers.get(f"{prefix}-Usage"))
        if limit and usage:
            return limit[0] - usage[0], limit[1] - usage[1]
    return None


def _pair(value: str | None) -> tuple[int, int] | None:
    parts = (value or "").split(",")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None

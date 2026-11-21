from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
ALLOWED_FETCH_SITES = frozenset({"same-origin", "none"})


def is_cross_site_write(method: str, headers: Headers) -> bool:
    if method in SAFE_METHODS:
        return False
    fetch_site = headers.get("sec-fetch-site")
    if fetch_site is not None:
        return fetch_site not in ALLOWED_FETCH_SITES
    origin = headers.get("origin")
    if origin is None:
        return False
    origin_host = urlsplit(origin).netloc
    return not origin_host or origin_host != headers.get("host")


class CrossSiteGuard:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and is_cross_site_write(scope["method"], Headers(scope=scope)):
            response = PlainTextResponse("Cross-site request refused", status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

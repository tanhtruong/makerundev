import ipaddress
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

MapKind = Literal["openstreetmap", "openfreemap", "custom_raster", "custom_style"]
Rendering = Literal["raster", "style"]
Field = Literal["url", "attribution"]

MAX_URL_LENGTH = 2000
MAX_ATTRIBUTION_LENGTH = 200
PLACEHOLDERS = ("{z}", "{x}", "{y}")
PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::1/128",
        "fe80::/10",
        "fc00::/7",
    )
)
PRIVATE_SUFFIXES = (".local", ".lan", ".home.arpa", ".internal")


@dataclass(frozen=True, slots=True)
class ResolvedSource:
    kind: MapKind
    rendering: Rendering
    url: str
    dark_url: str | None
    attribution: str
    provider: str
    terms_url: str | None
    privacy_url: str | None


PRESETS: dict[MapKind, ResolvedSource] = {
    "openstreetmap": ResolvedSource(
        kind="openstreetmap",
        rendering="raster",
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        dark_url=None,
        attribution="© OpenStreetMap contributors",
        provider="OpenStreetMap",
        terms_url="https://operations.osmfoundation.org/policies/tiles/",
        privacy_url="https://wiki.osmfoundation.org/wiki/Privacy_Policy",
    ),
    "openfreemap": ResolvedSource(
        kind="openfreemap",
        rendering="style",
        url="https://tiles.openfreemap.org/styles/liberty",
        dark_url="https://tiles.openfreemap.org/styles/dark",
        attribution="OpenFreeMap © OpenMapTiles Data from OpenStreetMap",
        provider="OpenFreeMap",
        terms_url="https://openfreemap.org/tos/",
        privacy_url="https://openfreemap.org/privacy/",
    ),
}

CUSTOM_RENDERING: dict[MapKind, Rendering] = {"custom_raster": "raster", "custom_style": "style"}


def resolve(kind: MapKind, url: str | None, attribution: str | None) -> ResolvedSource:
    preset = PRESETS.get(kind)
    if preset is not None:
        return preset
    if url is None or attribution is None:
        raise ValueError(f"custom map source {kind} is missing its url or attribution")
    return ResolvedSource(
        kind=kind,
        rendering=CUSTOM_RENDERING[kind],
        url=url,
        dark_url=None,
        attribution=attribution,
        provider=urlsplit(url).hostname or url,
        terms_url=None,
        privacy_url=None,
    )


def rule_errors(kind: MapKind, url: str | None, attribution: str | None) -> dict[Field, str]:
    errors: dict[Field, str] = {}
    if kind in PRESETS:
        if url is not None:
            errors["url"] = "OpenStreetMap and OpenFreeMap come with their own address."
        if attribution is not None:
            errors["attribution"] = "OpenStreetMap and OpenFreeMap come with their own attribution."
        return errors
    url_error = _url_error(kind, url)
    if url_error is not None:
        errors["url"] = url_error
    attribution_error = _attribution_error(attribution)
    if attribution_error is not None:
        errors["attribution"] = attribution_error
    return errors


def _url_error(kind: MapKind, url: str | None) -> str | None:
    if url is None:
        return "Paste the address of the tiles or the style."
    if len(url) > MAX_URL_LENGTH:
        return "Keep the address to 2,000 characters or fewer."
    try:
        parts = urlsplit(url)
        _ = parts.port
    except ValueError:
        return "That is not a web address."
    if parts.scheme not in ("https", "http"):
        return "Use an https:// address, or http:// only for an address on your own network."
    if not parts.hostname:
        return "The address needs a host name."
    if parts.username is not None or parts.password is not None:
        return "Leave the user name and password out of the address."
    if parts.fragment or url.endswith("#"):
        return "Remove the # and what follows it from the address."
    if parts.scheme == "http" and not is_private_host(parts.hostname):
        return "Use an https:// address, or http:// only for an address on your own network."
    if kind == "custom_raster" and not all(p in url for p in PLACEHOLDERS):
        return "A raster tile address needs {z}, {x} and {y}."
    if kind == "custom_style" and any(p in url for p in PLACEHOLDERS):
        return "A style address points to one style file, without {z}, {x} or {y}."
    return None


def _attribution_error(attribution: str | None) -> str | None:
    if attribution is None or not attribution.strip():
        return "Write who the map data and tiles are from, as the provider asks."
    if len(attribution.strip()) > MAX_ATTRIBUTION_LENGTH:
        return "Keep the attribution to 200 characters or fewer."
    if "<" in attribution or ">" in attribution:
        return "Write the attribution as plain text, without HTML."
    return None


def is_private_host(hostname: str) -> bool:
    host = hostname.lower().rstrip(".")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "." not in host or host.endswith(PRIVATE_SUFFIXES)
    return any(address in network for network in PRIVATE_NETWORKS)

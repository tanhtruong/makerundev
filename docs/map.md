# The map

The activity page can draw the route over an interactive map. It is off until you pick a tile source under **Settings → Map**; until then the page draws the route as a shape and makes no request to any other host. [ADR 9](adr/0009-map-view.md) records why.

## Sources

| Source | What it is |
| --- | --- |
| No map | The default. The route shape, nothing sent anywhere. |
| OpenStreetMap | The standard raster tiles from `tile.openstreetmap.org`, under the [OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/). |
| OpenFreeMap | Vector tiles and styles from `tiles.openfreemap.org`, with a dark style when your system is in dark mode. |
| Custom raster tiles | Any XYZ tile template with `{z}`, `{x}` and `{y}`, such as a keyed provider or your own tile server. Tiles are 256 px, up to zoom 19. |
| Custom map style | The address of a MapLibre `style.json`. |

A custom source needs an attribution, shown on the map as plain text: write the credit your provider asks for. The server knows the preset addresses and credits, so a preset that moves is fixed by updating makerundev, and a custom source is the way out in the meantime.

The app proxies and caches nothing: your browser fetches tiles straight from the provider, and sends its default Referer, which carries this instance's origin but never the page path. The provider must allow cross-origin requests (CORS), because MapLibre reads tiles as images it draws with WebGL. Browsers without WebGL2 get the route shape.

## Before you pick one

The settings page shows this notice under the source you pick, before you save:

> Map tiles are loaded by your browser straight from {provider}. Each time you open an activity, {provider} receives your IP address, your browser's details, this instance's address, and which tiles you view, which shows where the route is to within a few hundred metres. Their terms and privacy policy apply. To keep everything on your server, use a local tile file instead.

For a custom source, `{provider}` is the host in the address and the terms sentence is left out. A style can also load tiles, fonts and icons from other hosts than its own, and each of them sees the same. The local tile file is not available yet ([#88](https://github.com/tanhtruong/makerundev/issues/88)).

## Keys in tile addresses

A keyed provider puts its API key in the address, such as `?key=...`. The address is stored in the instance's database and returned in full by `GET /api/map-source`, so **anyone who can open this instance can read the key**. Use a key restricted to your instance's domain where the provider offers one.

## Addresses the server accepts

- `https://` addresses, with a query string if the provider needs one.
- `http://` only for a host that is plainly on your own network: an IP address in `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`, `fe80::/10`) or an IPv6 unique local address (`fc00::/7`); `localhost`; a name ending in `.local`, `.lan`, `.home.arpa` or `.internal`; or a name with no dot, such as `http://tileserver`. The server looks only at the address and makes no DNS lookup.
- No user name or password, no `#` fragment, and at most 2,000 characters.

A raster address must contain `{z}`, `{x}` and `{y}`; a style address must not.

## The check on save

When you save a custom source, your browser tries it first: a raster source loads the zoom-0 tile, and a style is fetched and must have `version` and `sources`. If that fails, the page says why and offers **Save anyway**, since a tile server on another network, or one that is down for the moment, can still be right.

**Mixed content:** when makerundev is served over `https://`, the browser blocks every `http://` tile address, private or not. Serve the tiles over `https://` too, or open makerundev over `http://` on your network.

## When tiles fail

If no tile loads (offline, the provider down, CORS refused), the route draws over a blank background with "Map tiles could not be loaded from {provider}". If a style address fails, the page shows the route shape with the same note. A few missing tiles show nothing.

## Unconfirmed

OpenStreetMap blocks tile requests without a Referer. Whether it accepts the Referer of an instance opened as `http://localhost` has not been confirmed; if OSM tiles fail there, open the instance by its network name or pick OpenFreeMap.

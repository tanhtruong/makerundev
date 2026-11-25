# 9. Opt-in map under the route

Date: 2026-11-21

## Status

Accepted

## Context

The activity page draws the route as an SVG shape with no map under it. A map needs tiles, and tiles come from a tile server that learns the viewer's IP address, their browser, the instance's address and which tiles were viewed. At zoom 14 to 16 a tile covers 2.4 km down to 600 m, so the tile requests show where the route runs, home included. makerundev is self-hosted and single-owner (ADR 4), and it makes no third-party request on its own today.

The front-end moves to a React single-page app in 0.8.0 (ADR 8). The activity page is ported there, the charts move to the client, and the built assets ship inside the wheel with no CDN.

Facts checked on 2026-11-21:

- **OpenStreetMap's standard raster tiles** (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) are the worldwide raster source with no key and a published usage policy; OpenTopoMap needs no key but publishes no policy, and USGS covers only the United States. The policy allows an app like this. It requires visible attribution and a Referer, and advises against hard-coding the URL. A browser request with no Referer got a blocked tile.
- **OpenFreeMap** serves vector tiles with no key, no cookies and no published limits.
- **Keyed providers** have free tiers, mostly non-commercial: Stadia, MapTiler, Thunderforest, CARTO and the Protomaps API. MapTiler, Thunderforest and CARTO forbid proxying or caching tiles on a server, and OSM discourages it.
- **A PMTiles file** holds a whole basemap in one file: 140 GB for the planet, 84 MB for Berlin at full zoom on a 2025 build, ODbL data from OpenStreetMap. Starlette 1.10 serves it with range requests, and the `pmtiles` JS protocol (8 KB) reads it in the browser. A vector style also needs fonts and sprites, which Protomaps hosts on GitHub.
- **Libraries**, gzipped:
  - Leaflet 1.9.4 is 42 KB, raster only. Its vector plugin cannot read MapLibre styles and is unconfirmed on Leaflet 2.
  - MapLibre GL JS 6.19 is 298 KB plus a 157 KB worker. It needs WebGL2, reads raster and vector sources and MapLibre styles, and loads its worker without `blob:` when served from the same origin.
  - OpenLayers 10.11 is 298 KB and reads MapLibre styles only through the `ol-mapbox-style` add-on.

## Decision

- **The map is context under one activity's route.** It is interactive (pan and zoom) and sits on the React activity page. It is never built in Jinja. A synced hover marker and a map of all activities are separate features.
- **No third-party request until the owner asks for one.** There is no map until the owner picks a tile source on the settings page. The choice is one row for the instance in the database, like the Garmin key, not an environment variable, and it moves to per user only if login arrives. Nothing is selected by default.
- **The route shape stays the fallback.** It shows when no source is set and when WebGL2 is missing. If tiles fail to load (offline, provider down), the route draws over a blank background with a short note.
- **Four kinds of source:**
  - **OpenStreetMap** raster, a preset.
  - **OpenFreeMap** vector, a preset.
  - **Custom**: an `https://` raster template containing `{z}`, `{x}` and `{y}`, or a MapLibre style URL, plus an attribution text the owner must fill in. This covers keyed providers without the app knowing them, and an API key sits in the URL in the instance's database. Plain `http://` is accepted only for a private network address. The browser checks the URL on save, because the app proxies nothing.
  - **A local PMTiles file** in the data directory.
- **The browser fetches tiles straight from the provider.** The app proxies and caches nothing: three providers forbid it, and a proxy hides little on a home server, where the browser and the server usually share one public IP. The browser's default Referer is kept for every source, because OSM blocks requests without one. It carries the instance's origin, never the page path.
- **The local file is served as-is.** The app serves the `.pmtiles` file with range requests, and the browser reads it with the `pmtiles` protocol, so the server has no tile code. The app ships the Protomaps basemap style, its sprites and one Latin font, so the owner only drops in the file. Labels in other scripts may be missing.
- **MapLibre GL JS, from npm.** It is the reference renderer for the MapLibre styles the vector sources use, and it reads raster sources too. Vite puts it in its own chunk, loaded only when a tile source is set, and it ships inside the wheel with the rest of the bundle.
- **Attribution is on the map.** MapLibre's attribution control shows each source's credit:
  - OpenStreetMap: "© OpenStreetMap contributors", linked to its copyright page.
  - OpenFreeMap: "OpenFreeMap © OpenMapTiles Data from OpenStreetMap".
  - A custom source: the owner's text.
  - A local file: the OpenStreetMap credit, because the data is ODbL.

  MapLibre's BSD-3 licence and the bundled font's OFL licence ship with the bundle's third-party licences.
- **The activity JSON carries route coordinates.** The activity detail endpoint returns the downsampled latitude and longitude points (at most about 600), and the client draws both the route shape and the map from them.
- **The owner is told before saving.** Under the source picker on the settings page, and in the docs:

  > Map tiles are loaded by your browser straight from {provider}. Each time you open an activity, {provider} receives your IP address, your browser's details, this instance's address, and which tiles you view, which shows where the route is to within a few hundred metres. Their terms and privacy policy apply ({link}). To keep everything on your server, use a local tile file instead.

  For a local file it says the tiles are served by this instance and nothing is sent to a third party. The activity page shows only the attribution.

## Consequences

- No map arrives before the React activity page, which is 0.8.0 at the earliest.
- Pages with a map load about 455 KB more script, gzipped; pages without one load nothing extra.
- Browsers without WebGL2 see the route shape only.
- An owner who picks a hosted source accepts that the provider sees their IP, the instance's address and roughly where they ran; the notice says so. Only a local file keeps tiles private, at the cost of downloading and updating it.
- The style, sprites and font grow the wheel and the image; the follow-up issue measures by how much.
- A provider that changes its terms or URL breaks its preset, not the app: the route shape still shows, and a custom URL is the way out.

## Amendments

### 2026-11-25

Settled while building the hosted sources (#70):

- **Custom is two explicit kinds.** The owner picks "Custom raster tiles" (a template with `{z}`, `{x}` and `{y}`) or "Custom map style" (a MapLibre style URL, which must not contain them), rather than the app guessing from the URL. The API's `kind` is `custom_raster` or `custom_style`.
- **A failed style URL falls back to the route shape**, with the note that tiles could not be loaded. Tiles that fail on a loaded style still draw the route over a blank background, as decided above.
- **The check on save warns but does not block.** The browser loads the zero-zoom tile or fetches the style; if that fails, the settings page names the reason (mixed content included) and offers "Save anyway", since a server the browser cannot reach now may still be right.

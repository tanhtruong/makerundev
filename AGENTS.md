# makerundev

Open source running analytics: a Python library and CLI (`packages/makerundev`) that parses FIT, GPX and TCX files into one record stream and computes metrics, and a self-hosted FastAPI app (`apps/server`) built on it. Read `docs/v1-spec.md` for scope and build order, `GLOSSARY.md` for terms, `docs/adr/` for decisions.

## Commands

- `make sync` - install the workspace
- `make check` - ruff, mypy strict, pytest; must pass before every push
- `make format` - apply ruff formatting and fixes
- `make openapi` - write the JSON API's schema to `apps/server/openapi.json`; run it after changing an `/api` route or model
- `make sync-web`, `make build-web`, `make check-web`, `make dev-web` - the React app in `apps/web` (Node and pnpm, `docs/frontend.md`); `make check-web` must pass before every push that touches `apps/web` or the OpenAPI schema
- `make serve` - run the app on http://127.0.0.1:8000 (`MAKERUNDEV_DATA_DIR`, `MAKERUNDEV_HOST`, `MAKERUNDEV_PORT`)
- `uv run makerundev --help` - the CLI
- `make release VERSION=x.y.z` - open the release PR: bumps both packages, pins the server to the same `makerundev` version and moves `[Unreleased]` in `CHANGELOG.md` under the version
- `make publish` - once that PR is merged, create the GitHub release `v<version>`, which ships PyPI and the GHCR image (`docs/releasing.md`)

## Architecture (decided - see ADRs before revisiting)

- Parsers map each format onto `STREAM_SCHEMA` in `makerundev/model.py`; metrics read only that stream and never branch on source format.
- Canonical units: UTC timestamps, degrees, metres, m/s, bpm, steps/min (both feet), watts, °C; ground contact time in ms, vertical oscillation in mm.
- FIT parsing uses `fitdecode`, never Garmin's SDK (licence, ADR 2).
- Untrusted XML is parsed with `defusedxml` only. Gzip and ZIP input is size-capped, and a ZIP must hold exactly one activity file.
- A React single-page app in `apps/web` replaces the server-rendered Jinja pages page by page (ADR 8); a Jinja page stays until its replacement merges. Bulletproof React structure enforced by ESLint, orval-generated client from `apps/server/openapi.json`, built into `apps/server/src/makerundev_server/web/` (`docs/frontend.md`). No CDN assets, and `make check` stays Python-only.
- Every `/api` route follows `docs/api.md`: a Pydantic response model, a camelCase operation id, one tag per front-end feature, units in field names, `{items, total}` lists.
- The library must not depend on the server's stack.
- Strava: the stream mapping is library code with no HTTP (`makerundev/io/strava.py`); OAuth, the HTTP client (`httpx2`) and the sync live in the server (ADR 6).
- Map: off until the owner picks a tile source in settings; the browser fetches tiles straight from the provider, the app proxies nothing, and the route shape stays the fallback (ADR 9).
- Garmin: the owner pastes their own Personal API key; the token, search and download calls live in the server on `httpx2`. A downloaded ZIP is unwrapped and imported as an ordinary file row, with no Garmin id stored (ADR 7).

## Issues

- Triage follows `docs/issues.md`: read it before opening, labelling or scheduling an issue, when a pull request closes one, and at `make publish`. Every open issue leaves with a type, area and contribution label, a milestone (or `roadmap` and a pending decision) and its fields on the roadmap board.

## Tests

- FIT fixtures are generated in tests with `fit-tool` (`conftest.py` at the root), not checked in as binaries.
- `packages/makerundev/tests/test_io.py` guards parsing, `test_metrics.py` the metric definitions, `test_format.py` how distances are named, `test_strava.py` the mapping of Strava streams and laps onto an activity, `test_cli.py` the CLI commands, `test_anonymize.py` that an anonymized copy moves every position and keeps every other byte, `apps/server/tests/test_upload.py` the import-to-page path and the JSON import's per-file results, `apps/server/tests/test_api.py` the JSON API's paging, the activity detail response and that `openapi.json` is not stale, `apps/server/tests/test_web.py` that the built web app answers every path the server does not own, redirects a trailing slash, and says how to build it when missing, `apps/web/src/lib/format.test.ts` that the web app formats numbers as `makerundev.format` does, `apps/web/src/app/routes/index.test.tsx` the activity list, its times in the athlete's timezone (UTC before Settings are saved) and its paging, `apps/web/e2e/` each React page's end-to-end path against a real server (the Strava page's through `apps/server/tests/strava_e2e_server.py` on the fake Strava), `apps/server/tests/test_charts.py` the SVG chart geometry, route sampling, and the thinned chart series and their axis bounds, `apps/server/tests/test_settings.py` athlete settings, their validation and TRIMP recompute, through the form and `/api/settings`, `apps/server/tests/test_load.py` zones, TRIMP, `/api/training-load` with its current VDOT and critical speed, and excluding an activity from them, `apps/server/tests/test_strava_sync.py`, `test_strava_match.py`, `test_strava_connection.py` and `test_strava_api.py` Strava sync and rate limits, matching against files, OAuth and disconnect, and the Strava status and actions as JSON (against the fake Strava in `strava_fake.py`, never the live API), `apps/server/tests/test_garmin_sync.py` and `test_garmin_api.py` Garmin sync, cursors and skips, and saving and removing the key through the JSON API (against the fake Garmin in `garmin_fake.py`, never the live API; `garmin_e2e_server.py` serves the app on that fake for the Garmin page's Playwright test), `apps/server/tests/test_cross_site.py` that unsafe requests from another site are refused and same-origin and header-less ones go through, `apps/server/tests/test_config.py` the pacelab-era environment variables and database name still being read, `apps/server/tests/test_migrations.py` that migrations match the models and that a 0.1.0 database still upgrades, `scripts/tests/test_release.py` the changelog rolling, release notes and the server's pin on the library version.

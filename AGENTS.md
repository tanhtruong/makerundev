# makerundev

Open source running analytics: a Python library and CLI (`packages/makerundev`) that parses FIT, GPX and TCX files into one record stream and computes metrics, and a self-hosted FastAPI app (`apps/server`) built on it. Read `docs/v1-spec.md` for scope and build order, `GLOSSARY.md` for terms, `docs/adr/` for decisions.

## Commands

- `make sync` - install the workspace
- `make check` - ruff, mypy strict, pytest; must pass before every push
- `make format` - apply ruff formatting and fixes
- `make serve` - run the app on http://127.0.0.1:8000 (`MAKERUNDEV_DATA_DIR`, `MAKERUNDEV_HOST`, `MAKERUNDEV_PORT`)
- `uv run makerundev --help` - the CLI
- `make release VERSION=x.y.z` - open the release PR: bumps both packages and moves `[Unreleased]` in `CHANGELOG.md` under the version
- `make publish` - once that PR is merged, create the GitHub release `v<version>`, which ships PyPI and the GHCR image (`docs/releasing.md`)

## Architecture (decided - see ADRs before revisiting)

- Parsers map each format onto `STREAM_SCHEMA` in `makerundev/model.py`; metrics read only that stream and never branch on source format.
- Canonical units: UTC timestamps, degrees, metres, m/s, bpm, steps/min (both feet), watts, °C; ground contact time in ms, vertical oscillation in mm.
- FIT parsing uses `fitdecode`, never Garmin's SDK (licence, ADR 2).
- Untrusted XML is parsed with `defusedxml` only. Gzip and ZIP input is size-capped, and a ZIP must hold exactly one activity file.
- The app is server-rendered (Jinja, inline SVG). No front-end build step, no CDN assets.
- The library must not depend on the server's stack.
- Strava: the stream mapping is library code with no HTTP (`makerundev/io/strava.py`); OAuth, the HTTP client (`httpx2`) and the sync live in the server (ADR 6).
- Map: off until the owner picks a tile source in settings; the browser fetches tiles straight from the provider, the app proxies nothing, and the route shape stays the fallback (ADR 9).
- Garmin: the owner pastes their own Personal API key; the token, search and download calls live in the server on `httpx2`. A downloaded ZIP is unwrapped and imported as an ordinary file row, with no Garmin id stored (ADR 7).

## Issues

- Triage follows `docs/issues.md`: read it before opening, labelling or scheduling an issue, when a pull request closes one, and at `make publish`. Every open issue leaves with a type, area and contribution label, a milestone (or `roadmap` and a pending decision) and its fields on the roadmap board.

## Tests

- FIT fixtures are generated in tests with `fit-tool` (`conftest.py` at the root), not checked in as binaries.
- `packages/makerundev/tests/test_io.py` guards parsing, `test_metrics.py` the metric definitions, `test_strava.py` the mapping of Strava streams onto the record stream, `test_cli.py` the CLI commands, `apps/server/tests/test_upload.py` the import-to-page path, `apps/server/tests/test_charts.py` the SVG chart geometry, `apps/server/tests/test_settings.py` athlete settings and TRIMP recompute, `apps/server/tests/test_load.py` zones, TRIMP and the training load page, `apps/server/tests/test_strava_sync.py`, `test_strava_match.py` and `test_strava_connection.py` Strava sync and rate limits, matching against files, and OAuth and disconnect (against the fake Strava in `strava_fake.py`, never the live API), `apps/server/tests/test_garmin_sync.py` and `test_garmin_connection.py` Garmin sync, cursors and skips, and saving and removing the key (against the fake Garmin in `garmin_fake.py`, never the live API), `apps/server/tests/test_cross_site.py` that unsafe requests from another site are refused and same-origin and header-less ones go through, `apps/server/tests/test_config.py` the pacelab-era environment variables and database name still being read, `apps/server/tests/test_migrations.py` that migrations match the models and that a 0.1.0 database still upgrades, `scripts/tests/test_release.py` the changelog rolling and release notes.

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
- Canonical units: UTC timestamps, degrees, metres, m/s, bpm, steps/min (both feet), watts, °C.
- FIT parsing uses `fitdecode`, never Garmin's SDK (licence, ADR 2).
- Untrusted XML is parsed with `defusedxml` only. Gzip input is size-capped.
- The app is server-rendered (Jinja, inline SVG). No front-end build step, no CDN assets.
- The library must not depend on the server's stack.

## Tests

- FIT fixtures are generated in tests with `fit-tool` (`conftest.py` at the root), not checked in as binaries.
- `packages/makerundev/tests/test_io.py` guards parsing, `test_metrics.py` the metric definitions, `test_strava.py` the mapping of Strava streams onto the record stream, `apps/server/tests/test_upload.py` the import-to-page path, `apps/server/tests/test_settings.py` athlete settings and TRIMP recompute, `apps/server/tests/test_load.py` zones, TRIMP and the training load page, `apps/server/tests/test_config.py` the pacelab-era environment variables and database name still being read, `apps/server/tests/test_migrations.py` that migrations match the models and that a 0.1.0 database still upgrades, `scripts/tests/test_release.py` the changelog rolling and release notes.

# pacelab

Open source running analytics: a Python library and CLI (`packages/pacelab`) that parses FIT, GPX and TCX files into one record stream and computes metrics, and a self-hosted FastAPI app (`apps/server`) built on it. Read `docs/v1-spec.md` for scope and build order, `GLOSSARY.md` for terms, `docs/adr/` for decisions.

## Commands

- `make sync` - install the workspace
- `make check` - ruff, mypy strict, pytest; must pass before every push
- `make format` - apply ruff formatting and fixes
- `make serve` - run the app on http://127.0.0.1:8000 (`PACELAB_DATA_DIR`, `PACELAB_HOST`, `PACELAB_PORT`)
- `uv run pacelab --help` - the CLI
- Releases: publishing a GitHub release `v<version>` ships PyPI and the GHCR image, see `docs/releasing.md`

## Architecture (decided - see ADRs before revisiting)

- Parsers map each format onto `STREAM_SCHEMA` in `pacelab/model.py`; metrics read only that stream and never branch on source format.
- Canonical units: UTC timestamps, degrees, metres, m/s, bpm, steps/min (both feet), watts, °C.
- FIT parsing uses `fitdecode`, never Garmin's SDK (licence, ADR 2).
- Untrusted XML is parsed with `defusedxml` only. Gzip input is size-capped.
- The app is server-rendered (Jinja, inline SVG). No front-end build step, no CDN assets.
- The library must not depend on the server's stack.

## Tests

- FIT fixtures are generated in tests with `fit-tool` (`conftest.py` at the root), not checked in as binaries.
- `packages/pacelab/tests/test_io.py` guards parsing, `test_metrics.py` the metric definitions, `apps/server/tests/test_upload.py` the import-to-page path.

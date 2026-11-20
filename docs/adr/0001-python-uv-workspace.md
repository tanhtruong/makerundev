# 1. Python, in one uv workspace with two packages

Date: 2026-11-19

## Status

Accepted

## Context

makerundev is both a library people install and a web app people self-host. The analysis side benefits most from Python's data ecosystem (polars, numpy) and most potential contributors from the running-data community already write Python.

## Decision

One repository, one [uv](https://docs.astral.sh/uv/) workspace, two distributions:

- `packages/makerundev`: library and CLI. Depends only on what parsing and metrics need.
- `apps/server`: `makerundev-server`, depends on `makerundev` plus the web stack.

Tooling: ruff for lint and format, mypy in strict mode, pytest. `make check` runs all of it and CI runs `make check`.

## Consequences

- Library users never pull in FastAPI or SQLAlchemy.
- The boundary between library and app is a package boundary, so the app can only use the library's public API.
- The web UI is server-rendered from Python, so there is no second language in the repository (see ADR 4).

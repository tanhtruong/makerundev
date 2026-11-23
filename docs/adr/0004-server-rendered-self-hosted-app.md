# 4. Server-rendered FastAPI app on SQLite

Date: 2026-11-19

## Status

Accepted. Its front-end half (Jinja pages and server-rendered SVG charts) is superseded by [ADR 8](0008-react-front-end.md); its data half stands.

## Context

The app is self-hosted, usually by one person on a home server or laptop. It must be easy to run and to back up, and contributors should not need a JavaScript toolchain.

## Decision

- FastAPI with Jinja templates; charts are inline SVG computed on the server. No front-end build step and no CDN, so the app works offline.
- SQLite holds one row per activity with its summary. The original upload is kept byte-for-byte (`data/originals/<sha256>`) as the source of truth, and the normalised stream is cached as Parquet (`data/streams/<sha256>.parquet`).
- Activities are keyed by the SHA-256 of the uploaded bytes, so importing the same file twice is a no-op.
- Backing up means copying the data directory.

## Consequences

- Recomputing metrics after a formula change is possible from the originals without asking users to re-import.
- Interactive charts (zoom, hover) will need a small client-side library later; it should be vendored, not loaded from a CDN.
- Schema changes need migrations; Alembic comes in before the next schema change (spec build order step 4).

# makerundev-server

A self-hosted web app for your running data, built on the [`makerundev`](../../packages/makerundev) library. Import FIT, GPX and TCX files, browse your activities and see pace, heart-rate and elevation charts, time in heart-rate zones and training load. Everything stays on your machine: there are no accounts, no external services and no CDN assets.

## Run it

From the repository root:

```bash
uv sync
uv run makerundev-server
```

Then open http://127.0.0.1:8000.

With Docker:

```bash
docker compose up
```

The image is also published as `ghcr.io/tanhtruong/makerundev-server` with each release.

## Configuration

| Variable | Default | What it does |
| --- | --- | --- |
| `MAKERUNDEV_DATA_DIR` | `./data` (`/data` in the image) | Where the database and imported files are kept |
| `MAKERUNDEV_HOST` | `127.0.0.1` (`0.0.0.0` in the image) | Address to listen on |
| `MAKERUNDEV_PORT` | `8000` | Port to listen on |

The project was called pacelab up to 0.2.0. `PACELAB_DATA_DIR`, `PACELAB_HOST` and `PACELAB_PORT` are still read when the `MAKERUNDEV_` variable is not set. The image sets all three `MAKERUNDEV_` variables, so override those there.

There is no login. Keep the app on `127.0.0.1` or behind a reverse proxy that adds authentication; the bundled `compose.yml` only publishes the port on localhost.

## Data

The data directory holds:

- `makerundev.db` - a SQLite database with one row per activity and its summary, and your athlete settings. A data directory created under the old name keeps its `pacelab.db`, which is used as it is. The app upgrades it to the latest schema on startup, so a newer version can open an older data directory, but not the other way round.
- `originals/` - each imported file as uploaded, named by its SHA-256
- `streams/` - the normalised record stream of each activity as Parquet

Importing the same file twice is detected by its hash and skipped. Uploads are capped at 64 MB per file. To back up, copy the whole directory; with Docker, `docker compose cp makerundev:/data ./makerundev-backup`.

## Routes

| Method and path | What it returns |
| --- | --- |
| `GET /` | Activity list and import form |
| `POST /activities` | Import one or more files (multipart field `files`) |
| `GET /activities/{id}` | Activity page with charts, best efforts, time in zones and TRIMP |
| `GET /load?days=90\|180\|365\|all` | Fitness, fatigue and form from daily TRIMP (default 180 days) |
| `GET /settings` | Athlete settings form |
| `POST /settings` | Save athlete settings and recompute TRIMP if needed |
| `GET /api/activities` | All activities with their summaries and TRIMP, as JSON |
| `GET /api/activities/{id}/records` | The activity's record stream, as JSON |

## Development

The app is FastAPI with Jinja templates and inline SVG charts; there is no front-end build step. `make check` at the repository root runs its tests along with the library's. See [CONTRIBUTING.md](../../CONTRIBUTING.md) and [ADR 4](../../docs/adr/0004-server-rendered-self-hosted-app.md).

### Changing the database schema

The schema is managed by Alembic migrations in `src/makerundev_server/migrations/versions/`, numbered `0001`, `0002`, and so on. After changing the models in `db.py`, from `apps/server`:

```bash
MAKERUNDEV_DATA_DIR=/tmp/makerundev-dev uv run alembic upgrade head
```

```bash
MAKERUNDEV_DATA_DIR=/tmp/makerundev-dev uv run alembic revision --autogenerate --rev-id NNNN -m "describe the change"
```

`NNNN` is the next number after the newest file in `versions/`. Read the generated file before committing: autogenerate misses some changes, such as renames, and SQLite changes run in batch mode, which copies the table. `tests/test_migrations.py` fails while the models and the migrations disagree, and checks that a 0.1.0 database still upgrades.

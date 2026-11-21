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
| `MAKERUNDEV_STRAVA_CLIENT_ID` | unset | Client id of your own Strava API application; enables [Strava sync](#strava-sync) |
| `MAKERUNDEV_STRAVA_CLIENT_SECRET` | unset | Its client secret |

The project was called pacelab up to 0.2.0. `PACELAB_DATA_DIR`, `PACELAB_HOST` and `PACELAB_PORT` are still read when the `MAKERUNDEV_` variable is not set. The image sets all three `MAKERUNDEV_` variables, so override those there.

There is no login. Keep the app on `127.0.0.1` or behind a reverse proxy that adds authentication; the bundled `compose.yml` only publishes the port on localhost.

So that another website cannot make your browser change anything here, every request other than `GET`, `HEAD` and `OPTIONS` is refused with 403 when the browser marks it as coming from another site (`Sec-Fetch-Site` other than `same-origin` or `none`), or, from a browser that does not send that header, when its `Origin` names a different host and port than the request's `Host`. A request with neither header, such as one from curl or a script, goes through. Behind a reverse proxy, make sure it passes the original `Host` header.

## Data

The data directory holds:

- `makerundev.db` - a SQLite database with one row per activity and its summary, your athlete settings, and your Strava tokens, Garmin key and sync progress once connected. A data directory created under the old name keeps its `pacelab.db`, which is used as it is. The app upgrades it to the latest schema on startup, so a newer version can open an older data directory, but not the other way round.
- `originals/` - each imported file as uploaded (for a ZIP, the file inside), named by its SHA-256, and each synced Strava activity's stream as gzipped JSON, named `strava-<id>`
- `streams/` - the normalised record stream of each activity as Parquet

Importing the same file twice is detected by its hash and skipped. Uploads are capped at 64 MB per file. To back up, copy the whole directory; with Docker, `docker compose cp makerundev:/data ./makerundev-backup`.

## Strava sync

Create a Strava API application under [Settings → My API Application](https://www.strava.com/settings/api), set its **Authorization Callback Domain** to the host you open the app on (`127.0.0.1` and `localhost` are always allowed by Strava), and start the app with `MAKERUNDEV_STRAVA_CLIENT_ID` and `MAKERUNDEV_STRAVA_CLIENT_SECRET`. The **Strava** page then offers **Connect with Strava** and **Sync now**. Behind a reverse proxy, make sure it passes the original host and scheme, because the OAuth redirect address is built from the request.

- **What a sync does.** It fetches activities newer than the newest one synced, then continues back through your history, newest first, with one request per activity for its streams. It runs in the background; the page refreshes while it does.
- **Rate limits.** Strava allows a new application 100 read requests per 15 minutes and 1,000 per day. A sync stops before either runs out and the next one continues where it stopped.
- **Files win.** A Strava activity is matched to one you imported from a file by the Strava id in a bulk-export filename, or by starting within 60 s and covering the same distance within 5% or 200 m, whichever is larger. The file's data is kept and gains a "View on Strava" link. Importing the file after a sync replaces the synced stream.
- **What is not synced.** Activities without streams, such as manual entries, are listed on the page and not tried again. The device name is not fetched. Edits and deletions made on Strava after an activity was synced are not picked up.
- **Disconnect.** Revokes the app's access and deletes the tokens and every activity that came only from Strava. Activities matched to a file stay.
- **Tokens.** They are stored unencrypted in the database in your data directory, and nowhere else.

## Garmin sync

Create a Personal API key in Garmin Connect on the web under **Settings → Personal API Key**, open the **Garmin** page and paste it. Saving exchanges the key for a 24-hour token at once, so a mistyped or expired key is turned away before it is stored. The page then offers **Sync now**.

- **What a sync does.** It fetches activities newer than the newest one synced, then continues back through your history, newest first. It walks Garmin's list by date window, not by position, so activities added or deleted on Garmin during a sync do not make it skip others. Each activity's original file is downloaded and imported exactly like an upload: a ZIP is stored as the file inside, under its own name, and deduplicated by its SHA-256. A file whose name would be all digits is stored as `garmin-<id>.<ext>`, so it is never mistaken for a Strava id. It runs in the background; the page refreshes while it does.
- **Pacing.** Garmin publishes no rate limits, so a sync waits a second between requests and stops when Garmin answers 429, saying when to try again if Garmin does. The next sync continues where it stopped.
- **Already here.** An activity that starts within 60 s of one you already have from a file, and covers the same distance within 5% or 200 m, is not downloaded. One that came only from Strava is replaced by the Garmin file, which keeps the Strava link.
- **What is not synced.** Manual entries have no file, and a download that cannot be read, such as a multi-sport ZIP holding several files or a file not sent as a ZIP, is skipped. Both are listed on the page and not tried again. Edits and deletions made on Garmin Connect after a sync are not picked up.
- **An expired key.** Keys last 30 to 365 days. When Garmin stops accepting yours, the sync stops and the page explains how to create a new one; paste it in and sync again.
- **Remove key.** Deletes the key, the token and the sync progress. Activities imported from Garmin stay, because they are ordinary files.
- **The key.** It is stored unencrypted in the database in your data directory, and nowhere else. It is never shown on a page.

## Routes

| Method and path | What it returns |
| --- | --- |
| `GET /` | Activity list and import form |
| `POST /activities` | Import one or more files (multipart field `files`) |
| `GET /activities/{id}` | Activity page with charts, best efforts, time in zones and TRIMP |
| `GET /load?days=90\|180\|365\|all` | Fitness, fatigue and form from daily TRIMP (default 180 days) |
| `GET /settings` | Athlete settings form |
| `POST /settings` | Save athlete settings and recompute TRIMP if needed |
| `GET /strava` | Strava connection, sync status and skipped activities |
| `POST /strava/connect` | Start connecting: redirects to Strava's authorisation page |
| `GET /strava/callback` | Where Strava sends you back after authorising |
| `POST /strava/sync` | Start a sync in the background |
| `POST /strava/disconnect` | Revoke access and delete Strava-only activities |
| `GET /garmin` | Garmin key form, sync status and skipped activities |
| `POST /garmin/key` | Check a Personal API key with Garmin and save it (form field `key`) |
| `POST /garmin/sync` | Start a sync in the background |
| `POST /garmin/remove` | Delete the key and sync progress; imported activities stay |
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

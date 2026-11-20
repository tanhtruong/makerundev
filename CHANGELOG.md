# Changelog

Notable changes to makerundev (pacelab up to 0.2.0), newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/). Before 1.0, a minor version may break the API or change a metric definition; the entry says so when it does.

A change to a metric definition is always listed, with how results shift for existing users.

## [Unreleased]

## [0.3.0] - 2026-11-21

### Added

- `makerundev-server`: sync from Strava with your own Strava API application (`MAKERUNDEV_STRAVA_CLIENT_ID`, `MAKERUNDEV_STRAVA_CLIENT_SECRET`). The new Strava page connects, syncs by hand in the background, lists activities that were skipped, and disconnects. A sync stops short of Strava's rate limits and the next one continues. Activities already imported from files are matched, not duplicated, and synced activities link to "View on Strava".
- `makerundev-server`: `external_source` and `external_id` in `GET /api/activities`.
- `makerundev.io.strava.read_strava(activity, streams)` maps a Strava activity and its streams (as returned by the Strava API) onto the record stream, with no network access of its own. Run cadence is doubled to steps per minute for both feet, as for files. `Activity.source_format` can now be `"strava"`.
- `makerundev-server`: an app icon, as the favicon (light and dark) and the home-screen icon.

### Changed

- `makerundev-server`: the database gains an identity for activities that do not come from a file (migration `0003`). It is upgraded on startup as usual, and no file on disk is renamed; back up the data directory first.
- **Breaking:** the project is renamed from pacelab to makerundev. The PyPI package, the import and the CLI are now `makerundev` (`pip install makerundev`, `from makerundev import load`, `makerundev summary`); the app is `makerundev-server` and its image `ghcr.io/tanhtruong/makerundev-server`. The `pacelab` package and `pacelab-server` image stop at 0.2.0. No metric definition changes.
- `makerundev-server` reads `MAKERUNDEV_DATA_DIR`, `MAKERUNDEV_HOST` and `MAKERUNDEV_PORT`, and names a new database `makerundev.db`. Existing installs keep working: the `PACELAB_` variables are still read when the new one is not set, an existing `pacelab.db` is used where it is, and `compose.yml` keeps the `pacelab-data` volume. With the image, which sets the `MAKERUNDEV_` variables itself, rename any `PACELAB_` variable you override. The Compose service is now `makerundev`; run `docker compose up -d --remove-orphans` once to replace the old container. Compose prefixes the volume with the checkout's folder name, so keep that folder's name, or pass `-p pacelab`, to stay on the same volume.

## [0.2.0] - 2026-11-20

### Added

- `pacelab-server`: a Settings page for max and resting heart rate, TRIMP coefficients, heart-rate zones (as % of max heart rate) and timezone. TRIMP is stored for each activity once heart rate is set, and recomputed when max heart rate, resting heart rate or the coefficients change.
- `pacelab-server`: time in heart-rate zones and TRIMP on the activity page, and a Training load page (`/load`) charting fitness, fatigue and form from daily TRIMP, by local day in the settings' timezone, over 90, 180 or 365 days or all history.
- `pacelab-server`: `trimp` in `GET /api/activities`.

### Changed

- `pacelab-server` shows activity start times in the athlete settings' timezone, and in UTC until settings are saved.
- `pacelab-server` manages its database schema with Alembic migrations and upgrades the database on startup. A data directory from 0.1.0 is upgraded in place with its activities kept; back it up before upgrading, as usual.

## [0.1.0] - 2026-11-19

### Added

- Parse FIT, GPX and TCX files, plain or gzipped, into one per-second record stream in canonical units (UTC, metres, m/s, bpm, steps/min, watts, °C).
- Metrics: summary (distance, elapsed and moving time, pace, heart rate), elevation gain and loss, best efforts from 400 m to the marathon, time in heart-rate zones, TRIMP, aerobic decoupling, and fitness/fatigue/form.
- Metric: grade-adjusted pace for running (Minetti et al. 2002 cost model, grade over a 60 m window), from `grade_adjusted_pace(activity)` and as `Summary.grade_adjusted_pace_s_per_km`. New: no existing values change, but code that builds a `Summary` itself must now pass the new field.
- CLI: `pacelab summary`, `pacelab efforts` and `pacelab export` (CSV or Parquet).
- `pacelab-server`: a self-hosted web app to import files, list activities and see pace, heart-rate and elevation charts, with a read-only JSON API.
- Docker image `ghcr.io/tanhtruong/pacelab-server`, keeping its data in a volume.

[Unreleased]: https://github.com/tanhtruong/makerundev/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/tanhtruong/makerundev/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tanhtruong/makerundev/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tanhtruong/makerundev/releases/tag/v0.1.0

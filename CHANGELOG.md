# Changelog

Notable changes to makerundev (pacelab up to 0.2.0), newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/). Before 1.0, a minor version may break the API or change a metric definition; the entry says so when it does.

A change to a metric definition is always listed, with how results shift for existing users.

## [Unreleased]

### Added

- Heart-rate zones can be a percentage of heart-rate reserve (Karvonen): pick the zone model in Settings, and each zone starts at resting + (max − resting) × the threshold. Settings also show the heart rate each zone starts at. Existing settings stay on % of max heart rate, so time in zones does not change until the model is switched.
- Activities synced from Strava have laps. Each activity now takes two Strava requests, its streams and its details, so a first sync of a long history takes about twice as many syncs. Activities synced before this release get their laps over the next syncs, after anything new and the backfill.
- `makerundev.io.strava.strava_laps(activity)` maps the laps of a Strava detailed activity onto `Lap`, and `read_strava` reads them when the activity it is given has them.
- `makerundev.format.zone_starts(boundaries_bpm)`, the whole-bpm heart rate each zone from zone 2 starts at, rounded up as `zone_range` labels them.
- Activities keep their name. The app shows the Strava name, the Garmin Connect name or a GPX file's track name in the activity list and on the activity page, and `GET /api/activities` returns it as `name` (`null` when there is none) next to `filename`. A Strava name is no longer lost when a Garmin file replaces the synced activity, and is now kept when Strava matches a file uploaded first. Names that were overwritten before this release cannot be recovered, and a GPX file imported before it keeps showing its file name.
- `makerundev.Activity.name`, the activity's name: a GPX file's first track name or, without one, its metadata name; the Strava activity's name for `read_strava`; `None` for FIT and TCX.
- `makerundev.metrics.critical_speed(efforts)` fits critical speed (m/s) and D′ (m) to a `{distance_m: time_s}` mapping such as `best_efforts` returns, using efforts of 2 to 20 minutes, and returns `makerundev.metrics.CriticalSpeed` or `None`.
- `makerundev.metrics.vdot(distance_m, time_s)`, Jack Daniels' VDOT from one maximal effort, by the Daniels & Gilbert formula. Efforts outside 3 minutes to 5 hours (`makerundev.metrics.VDOT_WINDOW_S`, both ends included), a distance that is not positive or not finite, a NaN time and an effort too slow to give a positive VDOT give `None`. VDOT is the VO2max at average running economy, not the VO2max a watch estimates.

## [0.6.0] - 2026-11-22

### Added

- `makerundev summary --long` (`-l`) adds grade-adjusted pace and aerobic decoupling to the end of each line, as `GAP 5:03 /km  decoupling +3.1%`, with `-` for a value the file cannot give (a sport other than running, no altitude or no heart rate).
- `makerundev zones FILE --max-hr N` prints the time in each heart-rate zone with its bpm range and share of the time that has heart rate. `--thresholds` takes ascending percentages of max heart rate (`62.5,75,87.5`, any count), by default 60, 70, 80 and 90 %.
- `makerundev trimp FILE --max-hr N --resting-hr N` prints the Banister TRIMP as a whole number; `--female` uses the female coefficients.
- Both commands exit with status 1 and say so when the file has no heart rate.
- `makerundev.metrics.DEFAULT_ZONE_THRESHOLDS`, the default zone thresholds the app and the CLI share, and `makerundev.format.zone_range(zone, boundaries_bpm)`, the bpm range label of a zone (`under 114 bpm`, `114-132 bpm`, `171 bpm and up`).
- `makerundev laps FILE` prints each lap the watch recorded with its distance, elapsed time and pace. A file with no laps, such as any GPX, prints nothing.
- `makerundev.Lap.pace_s_per_km`, a lap's duration per kilometre with pauses included, which the app and the CLI share.
- `makerundev summary`, `splits` and `laps` take `--units km|mi`, or read it from `MAKERUNDEV_UNITS`. With `mi` they print distance in miles and pace per mile, `splits` splits every mile and `summary --long` prints grade-adjusted pace per mile. Climb stays in metres.
- `makerundev.format.Unit` (`km`, `mi`), which `format.distance` and `format.pace` take, kilometres by default; `Unit.metres` is its length in metres. `makerundev.format.METRES_PER_MILE` is 1609.344.
- `makerundev anonymize FILE OUTPUT` writes a copy of a GPX or TCX file that is safe to attach to a bug report. Every position, and the GPX bounds, moves by one random rotation of the globe of at least 1000 km, written with as many decimals as the most precise coordinate in the file; distances, times, heart rate, comments and every other byte stay as they were, so a parser bug still reproduces. It reads the same plain, gzip and ZIP input as `load()`, writes plain XML, refuses an OUTPUT that exists, and lists what else could identify you (names and notes, author and links, device serial, time zone). FIT files are refused for now. `makerundev.io.anonymize(data)` does the same in code and returns the new bytes, the number of positions and that list.
- `makerundev-server` is published to PyPI with each release, so `uvx makerundev-server` runs the app without a clone. It requires the `makerundev` release of the same version.

### Changed

- `makerundev.format.kilometres` is now `makerundev.format.distance(meters, unit)`; there is no alias.
- `makerundev.format.distance_name` names any whole number of miles (`2 miles`), not only `1 mile`.

### Security

- `makerundev-server` refuses, with 403, any request other than `GET`, `HEAD` and `OPTIONS` that another website makes your browser send, so a page elsewhere can no longer import files, change settings, start a sync, or disconnect Strava or remove the Garmin key behind your back. It trusts the browser's `Sec-Fetch-Site` header, or, from older browsers, compares `Origin` with `Host`. Requests with neither header, from curl or scripts, are unaffected. Behind a reverse proxy, pass the original `Host` header.

## [0.5.0] - 2026-11-21

### Added

- `load()` reads a ZIP holding one FIT, GPX or TCX file, as Garmin Connect's *Export Original* gives it. The file is recognised by its content, not its name. A ZIP with more than one activity file (a bulk export), more than 16 files, a central directory over 64 KB, ZIP64, an entry compressed other than stored or deflated, an encrypted entry or more than 256 MB decompressed is refused with `ActivityFileError`, as is any damaged ZIP. `makerundev.io.unzip(data)` returns the file's name and bytes, or `None` when the data is not a ZIP. The CLI reads ZIPs too.
- `makerundev-server`: upload a single-activity ZIP. It is stored and deduplicated as the file inside, under that file's name, so uploading the ZIP and then the extracted file imports the run once.
- `makerundev-server`: sync from Garmin Connect with your own Garmin Personal API key. The new Garmin page saves the key (checked with Garmin first, never shown again), syncs by hand in the background about one activity a second, lists activities that were skipped, and removes the key. Each activity is downloaded as the original file and imported like an upload, so it has laps, the device and running dynamics. Activities you already have from a file are not downloaded again, and one that came only from Strava is replaced by the Garmin file. Removing the key keeps the imported activities.

### Changed

- `makerundev-server`: the database holds the Garmin key and sync progress (migration `0006`). It is upgraded on startup as usual; back up the data directory first.

## [0.4.0] - 2026-11-21

### Added

- `Activity.laps` holds the laps the watch recorded (auto-lap or the lap button) as `makerundev.Lap`s, with start time, elapsed time and distance as the device reported them. Read from FIT and TCX files; GPX has no laps and Strava laps are not synced yet, so those give none. `Activity.from_rows` takes `laps`.
- `makerundev.metrics.splits(activity, every_m=1000.0)` splits an activity's distance into 1 km splits counted from the start, plus whatever distance remains, with each split's distance, elapsed time, moving time and pace. Works for every sport. The time each boundary is crossed is interpolated between records, and pace is moving time per kilometre, so pauses are left out.
- The record stream has three running dynamics columns, read from FIT files that carry them: `ground_contact_time` (ms), `vertical_oscillation` (mm) and `step_length` (m). They are null for GPX, TCX and Strava.
- `Summary` has `avg_ground_contact_time` (ms), `avg_vertical_oscillation` (mm) and `avg_step_length` (m), weighted over moving intervals like `avg_cadence`, with zeros left out as dropouts. They are `None` when an activity has no running dynamics. Metrics treat a missing stream column as all null, so streams without the running dynamics columns still summarize.
- `makerundev splits FILE` prints each kilometre's distance, moving time and pace.
- `makerundev-server`: the activity page lists the laps of a file with two or more, with each lap's time, distance and pace. Activities imported earlier get their laps from the kept original the first time their page opens.
- `makerundev-server`: the activity page shows average ground contact time, vertical oscillation and step length when the activity has running dynamics. Streams of FIT files imported earlier gain the columns from the kept original the first time they are read, by the activity page or `/api/activities/{id}/records`; GPX, TCX and Strava activities keep streams without them.
- `makerundev-server`: the activity page shows a Splits table, with each kilometre's distance, moving time and pace, above the laps. It is computed when the page opens, so activities imported earlier get it too. Activities of 1 km or less have none.
- `makerundev-server`: the activity page draws the route shape from the GPS track, north up, as an inline SVG with no map tiles. Activities without positions, such as treadmill runs, show none.

### Changed

- `makerundev-server`: the database keeps each activity's laps (migration `0005`). It is upgraded on startup as usual; back up the data directory first.

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

[Unreleased]: https://github.com/tanhtruong/makerundev/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/tanhtruong/makerundev/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/tanhtruong/makerundev/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/tanhtruong/makerundev/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/tanhtruong/makerundev/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tanhtruong/makerundev/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tanhtruong/makerundev/releases/tag/v0.1.0

# makerundev v1 spec

## Goal

Give runners full, private access to the telemetry their watch records, with metrics that are defined in the open and tested, and a self-hosted app to look at it. No account, no cloud and no vendor lock-in.

## Users

1. **Runners who self-host**: import a Strava or Garmin export, browse every run, and track fitness over time.
2. **Developers and data people**: `pip install makerundev`, load files into polars, build their own analysis.

## Scope

### Data sources

| Source | v1 | How |
| --- | --- | --- |
| FIT files | Done | `fitdecode` (MIT). Covers Garmin, Coros, Suunto, Polar, Wahoo. Reads running dynamics (ground contact time, vertical oscillation, step length) into the record stream. |
| GPX files | Done | Own parser on `defusedxml`, reads the Garmin TrackPointExtension (heart rate, cadence, temperature, power). |
| TCX files | Done | Own parser on `defusedxml`, reads the ActivityExtension (speed, run cadence, watts). |
| Gzipped files | Done | Detected by magic bytes. Covers Strava bulk exports. |
| ZIP files | Done | One activity file per ZIP, as Garmin's *Export Original* and Personal API return it. Stored and deduplicated as the file inside. |
| Strava sync | Done | OAuth 2 with the instance owner's own Strava API application (client id and secret in env vars). Pulls the activity list and per-activity streams and maps the streams onto the record stream. Stops short of Strava's rate limits; tokens are stored locally only. See [ADR 6](adr/0006-strava-sync.md). |
| Garmin Connect sync | Done | Garmin's Personal API with the instance owner's own key, pasted into the app and stored locally only. Lists activities and downloads each one's original file, which goes through the normal file import. Paced at one request a second; stops on a 429 or an expired key. File export and import stays the documented path. See [ADR 7](adr/0007-garmin-personal-api-sync.md). |
| Apple Health / HealthKit | Later | Needs an iOS companion app. |

### Metrics

All definitions live in [GLOSSARY.md](../GLOSSARY.md). v1 ships:

- Summary: distance, elapsed and moving time, pace, average and max heart rate, average cadence and power, climb and descent.
- Best efforts: 400 m, 1 km, 1 mile, 5 km, 10 km, half marathon, marathon.
- Splits: moving time and pace per kilometre, the last split being whatever distance remains.
- Running dynamics averages: ground contact time, vertical oscillation and step length, where the FIT file has them.
- Time in heart-rate zones.
- TRIMP (Banister, with male and female coefficients).
- Aerobic decoupling.
- Grade-adjusted pace (Minetti cost model).
- Estimated power without a power meter (van Dijk and van Megen's model).
- Training load: fitness, fatigue, form.
- Critical speed and D′ from maximal efforts of 2 to 20 minutes.
- VDOT (Daniels & Gilbert) from one maximal effort of 3 minutes to 5 hours.

### Self-hosted app

- Import one or many files; duplicates (same bytes) are skipped.
- Activity list and activity page with pace, heart rate and elevation charts, the route shape, splits, laps, running dynamics averages, best efforts, average power, estimated power, time in zones and TRIMP.
- Training load page: fitness, fatigue and form over time from daily TRIMP.
- Athlete settings: max and resting heart rate, TRIMP coefficients, zones, timezone and body mass; TRIMP is stored per activity and recomputed when its inputs change, while estimated power is worked out when the page opens.
- Strava sync page: connect, sync by hand, see what was skipped, disconnect.
- Garmin sync page: save a Personal API key, sync by hand, see what was skipped, remove the key.
- JSON API: `GET /api/activities`, `GET /api/activities/{id}/records`.
- One process, SQLite, files on local disk. Runs with `uv run makerundev-server` or Docker.

Next: map view, search and filters, multi-user with login.

## Non-goals

- A social network: no feeds, kudos or segments leaderboards.
- Hosting other people's data. makerundev is self-hosted software, not a service.
- Training-plan generation.

## Build order

1. ~~Parsers, record stream, core metrics, CLI~~
2. ~~Self-hosted app: import, list, activity page~~
3. ~~Athlete settings, zones and TRIMP per activity, fitness/fatigue/form page~~
4. ~~Database migrations (Alembic) before the schema changes again~~
5. ~~Strava sync~~
6. ~~Grade-adjusted pace, splits and laps, running dynamics~~
7. ~~Garmin Connect sync with a personal API key~~
8. ~~First PyPI release of `makerundev`, container image for `makerundev-server`~~

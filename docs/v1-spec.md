# pacelab v1 spec

## Goal

Give runners full, private access to the telemetry their watch records, with metrics that are defined in the open and tested, and a self-hosted app to look at it. No account, no cloud and no vendor lock-in.

## Users

1. **Runners who self-host**: import a Strava or Garmin export, browse every run, and track fitness over time.
2. **Developers and data people**: `pip install pacelab`, load files into polars, build their own analysis.

## Scope

### Data sources

| Source | v1 | How |
| --- | --- | --- |
| FIT files | Done | `fitdecode` (MIT). Covers Garmin, Coros, Suunto, Polar, Wahoo. |
| GPX files | Done | Own parser on `defusedxml`, reads the Garmin TrackPointExtension (heart rate, cadence, temperature, power). |
| TCX files | Done | Own parser on `defusedxml`, reads the ActivityExtension (speed, run cadence, watts). |
| Gzipped files | Done | Detected by magic bytes. Covers Strava bulk exports. |
| Strava sync | Planned | OAuth 2 with the instance owner's own Strava API application (client id and secret in env vars). Pull the activity list and per-activity streams, map streams onto the record stream. Respect Strava's rate limits and API agreement; store tokens locally only. |
| Garmin Connect sync | Planned, optional | Garmin's official API needs approval through the Garmin Connect Developer Program, which is aimed at businesses. The community `garminconnect` library logs in with the user's own credentials and breaks whenever Garmin changes its login flow. Ship it as an optional extra, clearly labelled unofficial, with credentials stored only on the user's machine. Bulk export plus file import stays the supported path. |
| Apple Health / HealthKit | Later | Needs an iOS companion app. |

### Metrics

All definitions live in [GLOSSARY.md](../GLOSSARY.md). v1 ships:

- Summary: distance, elapsed and moving time, pace, average and max heart rate, average cadence and power, climb and descent.
- Best efforts: 400 m, 1 km, 1 mile, 5 km, 10 km, half marathon, marathon.
- Time in heart-rate zones.
- TRIMP (Banister, with male and female coefficients).
- Aerobic decoupling.
- Grade-adjusted pace (Minetti cost model).
- Training load: fitness, fatigue, form.

Next in line: running power from pace and grade when no power meter is present, VO2max estimate from race results, critical speed, splits and laps, running dynamics (ground contact time, vertical oscillation, stride length) where the FIT file has them.

### Self-hosted app

- Import one or many files; duplicates (same bytes) are skipped.
- Activity list and activity page with pace, heart rate and elevation charts and best efforts.
- Athlete settings: max and resting heart rate, TRIMP coefficients, zones and timezone; TRIMP is stored per activity and recomputed when its inputs change.
- JSON API: `GET /api/activities`, `GET /api/activities/{id}/records`.
- One process, SQLite, files on local disk. Runs with `uv run pacelab-server` or Docker.

Next: time in zones and TRIMP on the activity page, fitness/fatigue/form chart, map view, Strava sync page, search and filters, multi-user with login.

## Non-goals

- A social network: no feeds, kudos or segments leaderboards.
- Hosting other people's data. pacelab is self-hosted software, not a service.
- Training-plan generation.

## Build order

1. ~~Parsers, record stream, core metrics, CLI~~
2. ~~Self-hosted app: import, list, activity page~~
3. Athlete settings, zones and TRIMP per activity, fitness/fatigue/form page
4. ~~Database migrations (Alembic) before the schema changes again~~
5. Strava sync
6. Grade-adjusted pace, splits and laps, running dynamics
7. Garmin Connect sync (optional extra)
8. First PyPI release of `pacelab`, container image for `pacelab-server`

# 5. One current set of athlete settings, with a zone model

Date: 2026-11-19

## Status

Accepted

## Context

Time in zones, TRIMP and training load need the runner's own max and resting heart rate, their zone thresholds and which day an activity belongs to. Real max and resting heart rate drift over the years, and runners use different zone systems (% of max, % of heart-rate reserve, threshold heart rate, 3 to 7 zones). The app is single-user until login arrives.

## Decision

- **One current set of settings.** A single-row `athlete_settings` table (`CHECK id = 1`). Changing an input to TRIMP (max heart rate, resting heart rate, coefficients) recomputes TRIMP for every activity, in the same transaction as the save, so stored TRIMP never lags the settings. Streams are read before the write transaction opens, and imports and saves are serialised in the process, which relies on the app running as one process (ADR 4). An activity whose stream cannot be read gets no TRIMP rather than blocking the save. Settings with "effective from" dates are deferred: they would be more rows in the same table.
- **No row means not configured.** The migration seeds nothing. Defaults (zones at 60/70/80/90 % of max, the server's timezone) live once, in `pacelab_server/settings.py`, and fill the form. Until heart rate is set, zones and TRIMP are not shown.
- **A zone model, named in the row.** `zone_model` has one value for now, `max_hr_percent`: five zones from four ascending thresholds, stored as a JSON list in `zone_thresholds`. Other systems or zone counts can be added as new values without reshaping the table. The form shows no picker until there is a second model.
- **The timezone decides the day.** Start times stay in UTC; daily training load buckets activities by their local date in the settings' IANA timezone. A run while travelling can land a day off, which is accepted. The `tzdata` package is a dependency so the names resolve on any platform.
- **TRIMP is stored, time in zones is not.** `activities.trimp` is stored because the load page sums it across all history; time in zones is computed from one stream when its activity page is opened. TRIMP is null for an activity with no heart-rate samples, so it is counted as missing rather than as a rest day's 0.
- **The zone maths stays in the server.** The library takes bpm boundaries and Banister coefficients; turning settings into those is server code until a second zone model makes a library helper worth a public API.

## Consequences

- Changing resting or max heart rate rewrites past TRIMP with today's values, so history is re-read in today's terms rather than as it was felt then.
- Saving heart-rate changes reads every activity's stream once. If that grows slow on large libraries, recomputation moves to a background task.
- A new zone model needs code in `settings.py` and the form, not a migration.

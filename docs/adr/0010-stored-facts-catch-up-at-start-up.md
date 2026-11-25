# 10. Reads never write; old rows catch up at start-up by facts version

Date: 2026-11-25

## Status

Accepted

## Context

The app keeps some facts on each activity's row so that the list and the training load page do not read every stream: summary figures, TRIMP (ADR 5), laps, best efforts, and running dynamics in the stored stream. Each was added in a different release, and each brought its own way of filling rows stored before it existed. Reading an activity's records filled running dynamics into old FIT streams, reading its laps filled laps, and the training load page filled best efforts, so three reads wrote to the database or the data directory. A change to how a fact is computed shipped a migration that cleared the column, and the next read filled it again. File imports and Strava sync each wrote a row with their own copy of the same steps.

## Decision

- **One module owns the stored facts.** `makerundev_server/facts.py` is the only code that sets them. A file upload, a Garmin file and a Strava activity all go through its writer, which sets every fact, writes the original and the stream, and stamps the row with the current facts version. Saving athlete settings asks it to recompute TRIMP.
- **Reads never write.** Opening an activity, its records or the training load page reads what is stored. A missing fact reads as empty.
- **Old rows catch up once, at start-up.** `activities.facts_version` holds the version a row was written under; the migration that added it starts existing rows at 0. Right after migrations and before the app serves, every row behind the current version is worked out again: summary figures, TRIMP and best efforts from its stream, laps and missing running dynamics from its original. Each row commits on its own.
- **A row that cannot catch up is marked current anyway.** Its stream or original is unreadable, or its original no longer lines up with its stream. It keeps what it has, leaves a missing fact empty, is logged, and is not tried again on the next start. Start-up never fails for one bad file.
- **A later change to how a fact is computed bumps the version.** It does not ship a migration that clears the column.
- **Strava sync imports, then records progress.** The activity is imported in one transaction and the sync cursor moves in a second, as Garmin sync does. A run stopped in between finds the activity by its Strava id on the next run and moves the cursor past it, with nothing duplicated or skipped.

## Consequences

- The first start after an upgrade that bumps the version is slower once, since every stream, and every file row's original, is read. Later starts read nothing.
- A Strava activity whose laps were never fetched keeps them unset through catch-up, so the sync's lap phase still fetches them.
- The activity detail serves stored best efforts; splits, time in zones, aerobic decoupling and estimated power stay computed on read.
- Strava's imported count can be one short after a run stopped between the two transactions; the activity itself is there once.

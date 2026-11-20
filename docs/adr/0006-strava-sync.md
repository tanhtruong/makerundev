# 6. Strava sync with the owner's own API application

Date: 2026-11-20

## Status

Accepted

## Context

Runners keep their history on Strava, and the bulk export is a manual step that goes stale. Strava's API gives the activity list and per-activity streams, behind OAuth and a rate limit of 100 reads per 15 minutes and 1,000 per day for a new application. makerundev is self-hosted and single-user (ADR 4), so there is no shared application to register and no server of ours to hold tokens. An activity synced from Strava has no file, while every activity so far was identified by the SHA-256 of its file.

## Decision

- **The instance owner registers their own Strava API application.** The client id and secret come from `MAKERUNDEV_STRAVA_CLIENT_ID` and `MAKERUNDEV_STRAVA_CLIENT_SECRET`. The scope is `activity:read_all`. The redirect URI is built from the request, and the OAuth `state` is stored in the database, so no signing key is needed. Tokens live only in the instance's database.
- **The mapping is library code, the network is server code.** `makerundev.io.strava` maps a Strava activity and its streams onto the record stream with no HTTP, like any other source (ADR 3). The server owns OAuth, the HTTP client and the sync.
- **An activity has an identity apart from its file.** `activities` gains `external_source` and `external_id`, unique together, and `storage_key`, which names the stream and the original on disk. `sha256` becomes nullable and is used only to detect the same file twice. `storage_key` is backfilled from `sha256`, so nothing on disk is renamed. A synced activity's original is its stream JSON, gzipped.
- **Sync is started by hand and runs in one background thread.** Each sync fetches activities newer than the newest one synced, then continues the backfill, newest first. Two cursors, `newest_synced` and `backfill_before`, are stored in a single-row `strava_connection` table with the tokens and the sync status, and a cursor moves only once its activity is committed. The sync stops when fewer than 5 requests remain in the 15-minute window or fewer than 20 in the day, or on a 429, and the next sync picks up from the cursors.
- **Streams only, no per-activity detail call.** One request per activity keeps a backfill of a thousand activities within about a day. The cost is that `device` is null for synced activities. `filename` holds the Strava activity name.
- **Every sport with streams is pulled.** Activities without streams (manual entries) or that fail to map are skipped, and the cursors move past them, so they are not retried. The most recent skipped activities are kept as a JSON list on the `strava_connection` row with the reason, for the sync page.
- **A file wins over Strava.** A Strava activity matches a file by the Strava id in a bulk-export filename, or by start time within 60 s and distance within the larger of 5% and 200 m. The file's row keeps its stream and records the Strava id. Uploading a file after a sync runs the same check and replaces the synced stream.
- **Strava is read once.** Edits and deletions made on Strava after a sync are ignored.
- **Disconnect removes what came from Strava.** It revokes the token, then deletes the tokens and every Strava-only activity with its files, also when the revoke call fails. Rows matched to a file stay and lose their Strava id.

## Consequences

- Setting up sync takes a few minutes on Strava's API settings page, which the app has to explain.
- A first sync of a long history takes several sessions, because of the rate limit.
- A renamed, edited or deleted Strava activity stays as it was first synced until the owner disconnects and syncs again.
- Two different activities that start within a minute and cover nearly the same distance would be treated as one. That is accepted for a single athlete.
- Tokens are stored unencrypted in the data directory, which is as private as the rest of it.

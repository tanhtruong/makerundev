# 7. Garmin sync with the owner's personal API key

Date: 2026-11-21

## Status

Accepted

## Context

The v1 spec planned Garmin Connect sync as an optional extra on the community `garminconnect` library, which logs in with the user's own credentials and breaks whenever Garmin changes its login flow. On 21 October 2026 Garmin opened a self-serve Personal API: the account holder creates a key in Garmin Connect (Settings → Personal API Key), with no application or approval. A key is shown once, there is one per account, and it expires after 30, 90, 180 or 365 days. Its Supplemental Terms limit it to tools the key holder develops or operates for their own use, which a self-hosted, single-user instance (ADR 4) fits.

Three calls cover a sync. `POST /personalapitoken-service/personal-api/personal-api-key/token` with `Authorization: ApiKey <key>` returns a JWT for `Authorization: Bearer` calls. `GET /activitylist-service/activities/search/activities` lists activities, paged by `start` and `limit`. `GET /download-service/files/activity/{activityId}` returns the activity's original file in a ZIP. There are no webhooks and no published rate limits.

A spike against a real account (534 activities over six years) found:

- The token is a bare JWT in a `text/plain` body, valid for 24 hours, with no claim saying when the key itself expires.
- Search returns the whole history, newest first, with the start time in `startTimeGMT` (`"2026-11-19 16:23:08"`, UTC, no offset) and a `manualActivity` flag.
- Each download is a ZIP holding one deflated entry, `{activityId}_ACTIVITY.fit`, which `load()` parses fully, laps and running dynamics included. The ZIP and its FIT are byte-identical to *Export Original* on the Connect website.
- About ten requests in a row drew no throttling and no rate-limit headers.

Strava sync (ADR 6) already settled cursors, a single-row connection table, a background thread and the sync page. Garmin differs in one way that matters: it hands back the original file, so a synced activity can be an ordinary file row.

## Decision

- **The owner pastes their own key; `garminconnect` is dropped.** The key is entered on a `/garmin` page, never in an environment variable, and stored only in the instance's database, in a single-row `garmin_connection` table with the cached token and its expiry, the sync cursors and status, counts and a skipped list. Saving the key exchanges it for a token at once, so a wrong key is rejected on save. The token is exchanged again when less than an hour of it is left. File export and import stays the documented path, and there is no unofficial login.
- **Three calls on `httpx2`, in the server.** No new dependency and no extra. The library gains no Garmin module, because the payload is a file the existing parsers read.
- **The library reads a single-activity ZIP.** `load()` detects a ZIP by its magic bytes and requires exactly one entry that sniffs as FIT, GPX or TCX by content, not by name. Directories are ignored. Limits: at most 16 entries, at most 256 MB read in total under a streaming limit that ignores the sizes in the ZIP header, and encrypted entries are rejected. Nothing is written to disk. A separate unwrap step returns the entry's name and bytes. Bulk-export ZIPs stay out of scope.
- **A ZIP is unwrapped before it is hashed, wherever it comes from.** An uploaded or synced ZIP is stored as its inner file, and `sha256` is that file's, so the same run dedupes whether it arrives as the ZIP, the extracted FIT or a sync. Gzip keeps hashing the raw bytes, as before.
- **A synced activity is an ordinary file row.** Garmin ids are not stored on activity rows; `external_source` and `external_id` stay Strava's. `filename` is the ZIP entry name, falling back to `garmin-{id}.{ext}`, so a Garmin file never has an all-digit stem that would be read as a Strava id.
- **Sync is started by hand and runs in its own background thread.** Like Strava, it first fetches activities newer than `newest_synced`, then continues the backfill below `backfill_before`, newest first. A cursor moves only once its activity is committed or skipped. Garmin and Strava syncs run independently, and the store's write lock serialises their commits.
- **What is already there is not downloaded again.** A list entry whose start time and distance match an existing file row (within 60 s, and within the larger of 5% and 200 m) counts as already imported and is not downloaded, so the file already there wins. A Strava-only row is replaced by the Garmin file, as an upload replaces it.
- **Every activity type is pulled.** Manual entries are skipped without a download. A download that fails to read is skipped with its reason, kept in the skipped list for the sync page and not retried; a multi-sport ZIP with several activity files is one such case.
- **Pace the requests, stop when told.** The sync waits 1 s between requests and stops on a 429, with Garmin's `Retry-After` in the message when there is one. There is no daily budget until Garmin publishes one.
- **An expired key is a message, not a date.** A 401 stops the sync, and the page explains how to create a new key. The key's expiry is not asked for or tracked, because the API does not report it.
- **Removing the key keeps the activities.** It deletes the key, the token, the cursors and the skipped list. Activities imported from Garmin are files the owner holds, and with no Garmin id on their rows they could not be told apart anyway.
- **Garmin is read once.** Edits and deletions made on Garmin Connect after a sync are ignored.

## Consequences

- Setting up Garmin sync is a paste, but the key has to be replaced every 30 to 365 days, and the owner learns of it when a sync fails.
- A first sync takes about one request per activity plus one per 99 listed, a second apart: around ten minutes for the spike account. If Garmin throttles, the next sync picks up from the cursors.
- Synced activities have a device and laps, which Strava-synced ones lack, because they come from the watch's file.
- Garmin activities cannot be removed in bulk by source; they are deleted like any other file.
- Uploading a ZIP now stores the file inside it. Earlier uploads are unchanged.
- The Personal API is new and undocumented beyond its Swagger page. A change to the token body, the search fields or the ZIP layout breaks sync, not file import.
- The key is tied to one Garmin account. When login arrives, each user needs their own key.

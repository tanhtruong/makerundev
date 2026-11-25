# JSON API convention

Every route under `/api` follows these rules, so that the React app's client can be generated from the OpenAPI schema and the API reads the same everywhere. [ADR 8](adr/0008-react-front-end.md) records why. `GET /api/activities` in `apps/server/src/makerundev_server/api.py` is the reference endpoint.

## Routes

- Every route has a Pydantic response model, declared as the function's return type.
- Its operation id is the function's name in camelCase: `list_activities` becomes `listActivities`. The router's `generate_unique_id_function` does this, so name the function for what the client will call.
- It has one tag, the front-end feature it serves: `activities`, `training-load`, `settings`, `strava`, `garmin` or `map`.
- It declares every error response it can return with `responses=`, with the `Problem` model for a `detail` error.
- Server-rendered pages are kept out of the schema (`include_in_schema=False`) until they are removed.

## Fields

- Names are snake_case.
- Values are in the canonical units of the record stream (listed in the README), with the unit at the end of the name: `distance_m`, `elapsed_s`, `pace_s_per_km`, `avg_heart_rate_bpm`. A unitless value, such as `trimp`, has no suffix.
- Times are UTC in ISO 8601, `2026-03-01T07:00:00Z`; dates without a time are `2026-03-01`.
- A value that can be missing is required and nullable (`float | None` with no default), so the client always gets the key.
- The client formats pace, duration, distance and local time for display. Every other derived number, including chart series thinned to about 1,000 points, is computed in Python, where it is tested, and returned ready to draw.

## Errors

- A 4xx error is FastAPI's `{"detail": "activity not found"}`, lower case with no full stop.
- A validation error is FastAPI's 422 list of `loc`, `msg` and `type`. Where a form shows the message next to a field, write our own `msg` rather than Pydantic's.
- A request the resource's current state refuses, such as starting a Strava sync before Strava is connected, is a 409.
- An outside service that could not be reached, or answered with an error, while the request waited on it is a 502 with a `detail`, such as `PUT /api/garmin/key` when Garmin cannot check the key.
- A route that acts on several items in one request, such as `POST /api/activities` importing files, answers 200 whenever the request itself is well formed, even when every item failed, and reports each item's outcome in the body in the order sent. A 4xx would make the generated client treat the response as an error and drop the per-item results.

## Lists

- A list returns `{"items": [...], "total": N}`, where `total` counts every item, not the page.
- It takes `limit` (default 50, at most 200) and `offset` (default 0); a value outside those is a 422.
- Its order is stable and ends on a unique column, so paging never skips or repeats an item.
- A list that can be sorted takes `sort`: the name of a response field, ascending, or with a leading `-`, descending, such as `sort=-distance_m`. Missing values sort last either way.
- Filters are query parameters named after the field and unit they filter, such as `min_distance_m`; a repeatable one, such as `sport`, is repeated rather than comma-joined. Dates are local days in the athlete's timezone, inclusive at both ends. A filter whose bounds are reversed, such as `from` after `to`, is a 422 on the first of them, with our own `msg`.
- `total` counts every item the filters match, not every item.
- `GET /api/activities/{id}/records` is the exception to this and to the response model rule: it returns the whole record stream, one untyped object per sample, as a plain list for scripts. The client uses the series an activity's own endpoint returns instead.

## Live status

A sync's progress is polled with an ordinary `GET`. There are no server-sent events or websockets.

- A status route polled while work runs, such as `GET /api/strava`, sends `Cache-Control: no-store`, so no cache serves a stale state.
- An action that starts background work, such as `POST /api/strava/sync`, answers 202 with the same body as the status route. Starting it again while it runs is the same 202, not an error: the client keeps polling.
- How the last sync ended is a code (`up_to_date`, `paused_short`, `rejected`, ...), not text. The client writes the words; `resume_at` says when a paused sync can go on, where the service told us.

## Requests from other sites

The app has no login. Every request other than `GET`, `HEAD` and `OPTIONS` that the browser marks as coming from another site is refused with 403 ([#78](https://github.com/tanhtruong/makerundev/issues/78)). A future login uses same-origin cookies, not bearer tokens, so the same guard keeps protecting it.

## Versions

`/api` is public, but has no `/v1` prefix before 1.0. A breaking change, such as a renamed field or a new response shape, gets an entry in `CHANGELOG.md`. Versioning starts at 1.0.

## The schema

`apps/server/openapi.json` is the committed schema. After changing a route or a model, run `make openapi` and commit the file with the change; `apps/server/tests/test_api.py` fails while it is stale.

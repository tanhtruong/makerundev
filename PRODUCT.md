# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

A runner who self-hosts makerundev for their own running data. They are usually technical enough to start it with `uvx` or Docker. They review runs and training load after the fact, mostly on a laptop or desktop and sometimes on a phone right after a run. Each instance has one owner and no login.

## Product Purpose

makerundev turns the owner's activity files and synced activities into running analytics they can trust and keep: the activity list, each run's splits, laps, heart rate, power and best efforts, and training load with current VDOT and critical speed. Success is an owner who checks their training here instead of a hosted service, and believes the numbers because they can see how each one is defined.

## Positioning

- **The data stays home.** It is self-hosted with no account. Originals are kept byte for byte, and nothing is sent to a third party unless the owner opts in, as with map tiles.
- **Open, tested metrics.** Every metric definition is public and tested with hand-computed values. A metric is named after the model it comes from, such as VDOT or critical speed, and an estimate never shares a name with a measured value.
- **One stream, any source.** FIT, GPX, TCX, Strava and Garmin all map onto one record stream, so a metric never depends on where a file came from.
- **One library behind everything.** The same Python library powers the CLI, the JSON API and the web app.

## Operating Context

- The owner imports files exported from a watch, or syncs from Strava or Garmin Connect, then browses activities and the training load page.
- The app runs on a home server or laptop, often on `127.0.0.1` or behind the owner's reverse proxy.
- The web app is a React single-page app (ADR 8) that ships inside the server's wheel and Docker image, so the owner never needs Node.

## Capabilities and Constraints

- Units in the app are metric: km, m and min/km. The CLI already offers miles; the app does not yet.
- Times are stored in UTC and shown in local time.
- Pages must work at phone width.
- There is no login. A future multi-user login is planned and not designed yet.
- Terms follow `GLOSSARY.md`.

## Brand Commitments

- The name is makerundev, lower case. It was called pacelab up to 0.2.0.
- The favicons in `apps/server/src/makerundev_server/static/` (orange, light and dark variants) are the current mark.

## Evidence on Hand

- Real activity data is the owner's own; screenshots use generated demo runs.
- There are no testimonials, user counts or benchmarks. Future work must not invent them.

## Product Principles

- Every number has a visible definition, and an estimate is labelled as one.
- The owner's data never leaves the instance without the owner choosing it.
- A missing value says why, or shows `-`. It is never silently zero.
- One way to see each fact. The same metric looks the same on every page and in the CLI.

## Accessibility & Inclusion

WCAG 2.2 AA for text contrast and keyboard use.

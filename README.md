# pacelab

[![CI](https://github.com/tanhtruong/pacelab/actions/workflows/ci.yml/badge.svg)](https://github.com/tanhtruong/pacelab/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)

Open source running analytics for the data your sports watch already records.

pacelab reads the activity files that Garmin, Coros, Suunto, Polar and Wahoo watches produce (FIT, GPX, TCX), turns them into one clean per-second record stream, and computes the metrics runners care about: moving time and pace, climb, best efforts, heart-rate zones, TRIMP, aerobic decoupling and fitness/fatigue/form.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/activity-dark.jpg">
  <img alt="pacelab activity page for an interval session: distance, moving time, pace, heart rate and climb, with pace, heart-rate and elevation charts" src="docs/images/activity-light.jpg">
</picture>

It comes in two parts:

| Part | What it is | Where |
| --- | --- | --- |
| `pacelab` | Python library and CLI. Parsing, normalisation, metrics. | [`packages/pacelab`](packages/pacelab) |
| `pacelab-server` | Self-hosted web app built on the library. Import files, browse activities, see charts. Your data stays on your machine. | [`apps/server`](apps/server) |

> Status: pre-alpha. The file formats and metrics below work; sync from Strava and Garmin Connect is next on the [roadmap](docs/v1-spec.md#build-order).

## Quick start

You need [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/tanhtruong/pacelab.git && cd pacelab
uv sync
```

Summarise one or more files:

```bash
uv run pacelab summary ~/Downloads/*.fit
```

```text
morning.fit  2026-03-01 07:00  running  11.60 km  59:58  5:10 /km  148 bpm  +26 m
```

Other commands: `pacelab efforts FILE` (fastest 400 m to marathon) and `pacelab export FILE out.parquet` (the normalised record stream as CSV or Parquet).

Run the web app:

```bash
uv run pacelab-server
```

Then open http://127.0.0.1:8000 and import files. Data is kept in `./data` (set `PACELAB_DATA_DIR` to move it).

Or with Docker:

```bash
docker compose up
```

The container keeps its data in the `pacelab-data` volume. Back it up with `docker compose cp pacelab:/data ./pacelab-backup`.

## Using the library

```python
from pacelab import load
from pacelab.metrics import best_efforts, summarize

activity = load("morning.fit")
activity.records  # polars DataFrame, one row per sample, canonical units
summarize(activity)  # distance, moving time, pace, heart rate, climb
best_efforts(activity)  # {400.0: 116.0, 1000.0: 290.5, 5000.0: 1533.0, ...}
```

The record stream always has the same columns and units, whatever the source file: `timestamp` (UTC), `latitude`, `longitude` (degrees), `distance` (m), `speed` (m/s), `altitude` (m), `heart_rate` (bpm), `cadence` (steps/min for running), `power` (W), `temperature` (°C).

## Getting your data out of your watch

- **Garmin**: Garmin Connect → activity → ⚙ → *Export Original* gives the FIT file. For everything at once, request a data export from your Garmin account's data management page.
- **Strava**: Settings → My Account → *Download or Delete Your Account* → *Request your archive*. The `activities/` folder holds `.fit.gz`, `.gpx.gz` and `.tcx.gz` files, which pacelab imports as they are.
- **Coros, Suunto, Polar, Wahoo**: each app can export single activities as FIT.

## Documentation

- [v1 spec](docs/v1-spec.md) - scope, metrics definitions, data sources and build order
- [Glossary](GLOSSARY.md) - the terms the code and docs use
- [Architecture decisions](docs/adr) - why things are the way they are
- [Changelog](CHANGELOG.md) - what changed in each release
- [Contributing](CONTRIBUTING.md)

## License

[Apache-2.0](LICENSE)

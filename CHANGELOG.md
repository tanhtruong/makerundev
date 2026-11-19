# Changelog

Notable changes to pacelab, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/). Before 1.0, a minor version may break the API or change a metric definition; the entry says so when it does.

A change to a metric definition is always listed, with how results shift for existing users.

## [Unreleased]

### Added

- Parse FIT, GPX and TCX files, plain or gzipped, into one per-second record stream in canonical units (UTC, metres, m/s, bpm, steps/min, watts, °C).
- Metrics: summary (distance, elapsed and moving time, pace, heart rate), elevation gain and loss, best efforts from 400 m to the marathon, time in heart-rate zones, TRIMP, aerobic decoupling, and fitness/fatigue/form.
- CLI: `pacelab summary`, `pacelab efforts` and `pacelab export` (CSV or Parquet).
- `pacelab-server`: a self-hosted web app to import files, list activities and see pace, heart-rate and elevation charts, with a read-only JSON API.
- Docker image `ghcr.io/tanhtruong/pacelab-server`, keeping its data in a volume.

[Unreleased]: https://github.com/tanhtruong/pacelab/commits/main

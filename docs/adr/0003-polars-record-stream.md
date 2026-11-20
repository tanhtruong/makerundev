# 3. One canonical record stream, as a polars DataFrame

Date: 2026-11-19

## Status

Accepted

## Context

FIT stores positions as semicircles and running cadence per foot. GPX has no distance or speed. TCX puts speed and run cadence in extensions. If metrics handled these differences, every metric would carry format-specific code.

## Decision

Each parser maps its format onto one fixed schema (`makerundev.model.STREAM_SCHEMA`): UTC timestamps, degrees, metres, m/s, bpm, steps per minute, watts, °C. `normalize_records` then sorts, de-duplicates timestamps, fills distance from GPS when the file has none, makes distance non-decreasing, and derives speed when absent. Metrics read only this stream.

The stream is a polars DataFrame: columnar, fast, typed, and it writes Parquet natively, which the app uses as its stream cache.

## Consequences

- A new source (Strava streams, Garmin Connect) only needs a mapping onto the schema.
- Metrics are format-agnostic and tested on hand-built streams.
- Users of the library get a DataFrame they can analyse directly.

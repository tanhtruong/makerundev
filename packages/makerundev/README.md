# makerundev

Parse sports-watch activity files (FIT, GPX, TCX) into one normalised record stream and compute running metrics.

```bash
pip install makerundev
```

```python
from makerundev import load
from makerundev.metrics import best_efforts, splits, summarize

activity = load("morning.fit")
print(summarize(activity))
print(best_efforts(activity))
print(splits(activity))
```

```bash
makerundev summary morning.fit
makerundev efforts morning.fit
makerundev splits morning.fit
makerundev laps morning.fit
makerundev export morning.fit records.parquet
makerundev anonymize run.gpx shifted.gpx
```

See the [project README](https://github.com/tanhtruong/makerundev) for the full documentation.

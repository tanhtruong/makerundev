# makerundev

Parse sports-watch activity files (FIT, GPX, TCX) into one normalised record stream and compute running metrics.

```bash
pip install makerundev
```

```python
from makerundev import load
from makerundev.metrics import best_efforts, summarize

activity = load("morning.fit")
print(summarize(activity))
print(best_efforts(activity))
```

```bash
makerundev summary morning.fit
makerundev efforts morning.fit
makerundev export morning.fit records.parquet
```

See the [project README](https://github.com/tanhtruong/makerundev) for the full documentation.

# makerundev

Parse sports-watch activity files (FIT, GPX, TCX) into one normalised record stream and compute running metrics.

```bash
pip install makerundev
```

```python
from makerundev import load
from makerundev.analysis import analyse
from makerundev.metrics import best_efforts, splits

activity = load("morning.fit")
print(analyse(activity, body_mass_kg=68, max_hr=188, resting_hr=48))
print(best_efforts(activity))
print(splits(activity))
```

```bash
makerundev summary morning.fit
makerundev efforts morning.fit
makerundev splits morning.fit
makerundev laps morning.fit
makerundev export morning.fit records.parquet
makerundev anonymize morning.fit shifted.fit
```

`anonymize` moves every position in a FIT, GPX or TCX file far away and keeps the rest byte for byte. It lists what it could not check, such as names, a device serial, and in a FIT file unknown messages and developer fields.

See the [project README](https://github.com/tanhtruong/makerundev) for the full documentation.

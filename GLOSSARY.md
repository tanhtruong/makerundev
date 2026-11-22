# Glossary

**Activity** - One recorded workout: its sport, start time, source device and record stream. Built by `makerundev.load` from a file, or by `Activity.from_rows`.

**Record stream** - The per-sample telemetry of an activity, a polars DataFrame with the canonical columns and units listed in the README. Every source format is normalised into it; nothing downstream knows which format a file came from.

**Source format** - Where an activity's record stream came from: a file read as `fit`, `gpx` or `tcx`; `strava` for an activity synced from Strava; or `rows` for one built in code with `Activity.from_rows`. A `strava` activity is built from the streams the Strava API returns, so it has no original file and only the channels Strava keeps. Garmin sync imports the original FIT file, so those activities are `fit`.

**Anonymized copy** - A GPX or TCX file with every position moved by one random rotation of the globe, at least 1000 km from the original, and nothing else changed, so distances and times are the same and a parser bug still reproduces. Made by `makerundev anonymize` for bug reports.

**Interval** - The span between two consecutive records. Metrics are computed over intervals, not samples: an interval's duration and distance are the differences between its two records, and its heart rate, cadence and power are those of its first record.

**Recording interval** - An interval no longer than 30 s. A longer gap means the watch was paused or lost signal; it counts toward elapsed time and nothing else.

**Moving interval** - A recording interval covered at 0.5 m/s or faster.

**Moving time** - The summed duration of moving intervals.

**Elapsed time** - Last record's time minus first record's time.

**Lap** - A segment the device recorded, by auto-lap or the lap button: its start time, duration (pauses included) and distance, taken as the device reported them and not checked against the record stream. Read from FIT and TCX; a lap without a start time is dropped.

**Lap pace** - A lap's duration per kilometre. Unlike pace, it includes pauses, because a lap carries only the duration the device reported.

**Pace** - Moving time per kilometre.

**Grade-adjusted pace** (GAP) - The flat-ground pace with the same energy cost as a run's moving pace. It uses the running cost model from Minetti et al. (2002), [Energy cost of walking and running at extreme uphill and downhill slopes](https://doi.org/10.1152/japplphysiol.01177.2001):

```text
C(g) = 155.4 g^5 - 30.4 g^4 - 43.3 g^3 + 46.3 g^2 + 19.5 g + 3.6   (J/kg/m)
grade-adjusted pace = moving time / (sum of interval distance * C(g) / C(0)), per kilometre
```

`g` is a moving interval's grade as a ratio, uphill positive: the altitude change across a 60 m window of distance centred on the interval, divided by the window's length, with altitude interpolated between records. Near either end of a stretch of consecutive moving intervals the window shifts to stay inside the stretch, and a stretch shorter than 60 m uses its overall slope, so a window never spans a pause or a recording gap. Grades are clamped to the -45% to +45% range Minetti measured. The window trades noise against detail: a wider one damps GPS altitude noise more but flattens short steep hills.

Defined for running sports only. Unavailable when an activity has no moving intervals or any moving interval lacks altitude at either end.

**Cadence** - Steps per minute, both feet. FIT, GPX and TCX files store running cadence per foot; the parsers double it.

**Running dynamics** - Ground contact time, vertical oscillation and step length, measured per record by a watch or heart-rate strap with an accelerometer. Read from FIT files as the device recorded them, zeros included; other sources have none.

**Ground contact time** - How long a foot stays on the ground in one step, in milliseconds. FIT calls it stance time.

**Vertical oscillation** - How far the torso moves up and down in one step, in millimetres.

**Step length** - The distance from one foot strike to the next, by the other foot, in metres. Speed in m/s is cadence times step length, divided by 60. Garmin Connect labels the same value "stride length"; a stride in the strict sense is two steps.

**Average ground contact time, vertical oscillation and step length** - The running dynamics of an activity's moving intervals, each interval weighted by its duration, like average cadence. A zero is a dropout, not a measurement, so zeros are left out. An activity without running dynamics, or with only zeros, has no average rather than one of zero.

**Climb** (elevation gain) - Ascent with altitude noise filtered out: a rise or fall counts only once it reaches 3 m from the last turning point.

**Split** - A fixed length of an activity's distance, 1 km by default, counted from the start; the last split is whatever distance remains. The time each boundary is crossed is interpolated between records. A split's pace is its moving time per kilometre, so unlike lap pace it leaves pauses out.

**Best effort** - The fastest time over a fixed distance anywhere within an activity, interpolated between samples.

**Critical speed** - The speed a runner can hold for a long time without fatigue building rapidly, in m/s: the slope of the straight line through the distance and time of maximal efforts lasting 2 to 20 minutes, both ends included, fitted by least squares. Unavailable with fewer than two such efforts of different durations, or when the line gives a speed or D′ that is not positive.

**D′** (D prime) - The distance a runner can cover faster than critical speed before exhaustion, in metres: where the same line crosses zero time.

**Heart-rate zone** - A heart-rate band bounded by user-chosen thresholds. A heart rate equal to a threshold belongs to the higher zone. In the app and the CLI, thresholds are percentages of max heart rate, by default 60, 70, 80 and 90 % (the starts of zones 2 to 5).

**Zone model** - How zone thresholds are expressed and turned into heart rates. The app supports `max_hr_percent` (five zones, thresholds as % of max heart rate); others, such as % of heart-rate reserve, may follow.

**Athlete settings** - The runner's max and resting heart rate, TRIMP coefficients, zone model and thresholds, and timezone, kept by the app. The timezone decides which local day an activity counts toward in training load.

**TRIMP** - Banister's training impulse: minutes weighted by heart-rate reserve, a single number for how hard a session was.

**Aerobic decoupling** - How much efficiency (speed per heartbeat) fell from the first half of the moving time to the second, as a percentage. Under 5 % on a long steady run is read as good aerobic endurance.

**Training load** - Daily stress numbers (for example TRIMP per day) fed into the fitness/fatigue model.

**Fitness** - 42-day exponentially weighted average of training load (often called CTL).

**Fatigue** - 7-day exponentially weighted average of training load (often called ATL).

**Form** - Fitness minus fatigue as it stood at the start of the day, before that day's training (often called TSB).

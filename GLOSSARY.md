# Glossary

**Activity** - One recorded workout: its sport, start time, source device, name and record stream. Built by `makerundev.load` from a file, or by `Activity.from_rows`.

**Activity name** - The title a runner knows an activity by, such as "Morning Run". Read from a GPX file's first track, or its metadata when the track has none; FIT and TCX files carry none. The app also takes it from Strava and from the Garmin Connect listing. Strava's name wins over any other; a Garmin name wins over the one in the file it downloads; otherwise an activity keeps the first name it was given. An activity without a name is shown by its file name.

**Record stream** - The per-sample telemetry of an activity, a polars DataFrame with the canonical columns and units listed in the README. Every source format is normalised into it; nothing downstream knows which format a file came from.

**Source format** - Where an activity's record stream came from: a file read as `fit`, `gpx` or `tcx`; `strava` for an activity synced from Strava; or `rows` for one built in code with `Activity.from_rows`. A `strava` activity is built from the streams the Strava API returns, so it has no original file and only the channels Strava keeps. Garmin sync imports the original FIT file, so those activities are `fit`.

**Anonymized copy** - A GPX or TCX file with every position moved by one random rotation of the globe, at least 1000 km from the original, and nothing else changed, so distances and times are the same and a parser bug still reproduces. Made by `makerundev anonymize` for bug reports.

**Interval** - The span between two consecutive records. Metrics are computed over intervals, not samples: an interval's duration and distance are the differences between its two records, and its heart rate, cadence and power are those of its first record.

**Recording interval** - An interval no longer than 30 s. A longer gap means the watch was paused or lost signal; it counts toward elapsed time and nothing else.

**Moving interval** - A recording interval covered at 0.5 m/s or faster.

**Moving time** - The summed duration of moving intervals.

**Elapsed time** - Last record's time minus first record's time.

**Lap** - A segment the device recorded, by auto-lap or the lap button: its start time, duration (pauses included) and distance, taken as the device reported them and not checked against the record stream. Read from FIT and TCX, and from the laps of a Strava activity; a lap without a start time is dropped.

**Lap pace** - A lap's duration per kilometre. Unlike pace, it includes pauses, because a lap carries only the duration the device reported.

**Pace** - Moving time per kilometre.

**Grade-adjusted pace** (GAP) - The flat-ground pace with the same energy cost as a run's moving pace. It uses the running cost model from Minetti et al. (2002), [Energy cost of walking and running at extreme uphill and downhill slopes](https://doi.org/10.1152/japplphysiol.01177.2001):

```text
C(g) = 155.4 g^5 - 30.4 g^4 - 43.3 g^3 + 46.3 g^2 + 19.5 g + 3.6   (J/kg/m)
grade-adjusted pace = moving time / (sum of interval distance * C(g) / C(0)), per kilometre
```

`g` is a moving interval's grade as a ratio, uphill positive: the altitude change across a 60 m window of distance centred on the interval, divided by the window's length, with altitude interpolated between records. Near either end of a stretch of consecutive moving intervals the window shifts to stay inside the stretch, and a stretch shorter than 60 m uses its overall slope, so a window never spans a pause or a recording gap. Grades are clamped to the -45% to +45% range Minetti measured. The window trades noise against detail: a wider one damps GPS altitude noise more but flattens short steep hills.

Defined for running sports only. Unavailable when an activity has no moving intervals or any moving interval lacks altitude at either end.

**Estimated power** - The running power a power meter would report, estimated from speed, grade and body mass, in watts: the average over a run's moving intervals, each weighted by its duration, like average power. It uses the model from van Dijk & van Megen, *The Secret of Running* (2017), as the authors describe it on [TrainingPeaks](https://trainingpeaks.com/blog/running-with-power-what-it-can-tell-us-about-our-human-limits) and [Stryd's blog](https://blog.stryd.com/2019/12/17/the-cost-of-running-up-and-down-hills/):

```text
P       = ECOR(i) · m · v + ½ · ρ · cdA · v³
ECOR(i) = 0.98 + (i / 100) · 9.81 · (45.6 + 1.16 i) / 100   (J/kg/m)
ρ = 1.205 kg/m³, cdA = 0.24 m²
```

`v` is a moving interval's speed in m/s, `m` the runner's body mass in kg and `i` the interval's grade in percent, taken as for grade-adjusted pace. The air term assumes still air and a fixed frontal area, so no height is needed; a treadmill run has no air term, since the runner does not move through the air. Defined for running sports only, and unavailable whenever grade-adjusted pace is. It is a model estimate: never stored as power and never part of average power. Stryd and Garmin each define running power their own way, so a meter's number differs from this one, and from the other meter's.

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

**VDOT** - Jack Daniels' running performance index, from one maximal effort lasting 3 minutes to 5 hours, both ends included. With `v` the effort's speed in m/min and `t` its duration in minutes, Daniels & Gilbert (*Oxygen Power*, 1979) give its oxygen cost and the fraction of VO2max a runner can sustain for `t` minutes:

```text
VO2  = -4.60 + 0.182258 v + 0.000104 v²
F    = 0.8 + 0.1894393 e^(-0.012778 t) + 0.2989558 e^(-0.1932605 t)
VDOT = VO2 / F
```

VDOT is the VO2max that would produce the effort at average running economy. A runner with better or worse economy has a different VO2max for the same VDOT, and it is not the VO2max Garmin or other vendors show. `F` exceeds 1 below about 11 minutes, as Daniels' model expects. Unavailable outside the 3-minute to 5-hour window, about the span of Daniels' tables (shorter efforts lean on anaerobic capacity), for an effort too slow to give a positive VDOT, and for a distance that is not positive or not finite or a time that is not a number.

**Heart-rate zone** - A heart-rate band bounded by user-chosen thresholds. A heart rate equal to a threshold belongs to the higher zone. Thresholds default to 60, 70, 80 and 90 % (the starts of zones 2 to 5). In the app they are percentages of max heart rate or of heart-rate reserve, as the zone model says; in the CLI, of max heart rate.

**Zone model** - How zone thresholds are expressed and turned into heart rates. The app has five zones and two models: `max_hr_percent`, where a zone starts at max × %, and `hr_reserve_percent` (Karvonen), where it starts at resting + (max − resting) × %. Changing the model keeps the thresholds as typed and moves their heart rates.

**Athlete settings** - The runner's max and resting heart rate, TRIMP coefficients, zone model and thresholds, timezone and body mass, kept by the app. The timezone decides which local day an activity counts toward in training load. Body mass, in kilograms, is optional and feeds estimated power; like heart rate it is one current value, so changing it changes estimated power for every past run.

**TRIMP** - Banister's training impulse: minutes weighted by heart-rate reserve, a single number for how hard a session was.

**Aerobic decoupling** - How much efficiency (speed per heartbeat) fell from the first half of the moving time to the second, as a percentage. Under 5 % on a long steady run is read as good aerobic endurance. Running activities only, like grade-adjusted pace.

**Training load** - Daily stress numbers (for example TRIMP per day) fed into the fitness/fatigue model.

**Fitness** - 42-day exponentially weighted average of training load (often called CTL).

**Fatigue** - 7-day exponentially weighted average of training load (often called ATL).

**Form** - Fitness minus fatigue as it stood at the start of the day, before that day's training (often called TSB).

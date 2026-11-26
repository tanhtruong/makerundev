import datetime as dt
import random
from zoneinfo import ZoneInfo

from demo_runs import DemoSport, Format, Route, Run, Segment

ZONE = ZoneInfo("Europe/Copenhagen")
HOME = (55.6761, 12.5683)
HISTORY_DAYS = 430
SHOWCASE_DAYS = 14
INJURY = (300, 258)
RACE_DAY = 150
HR = int | tuple[int, int]


def speed(pace_s_per_km: float) -> int:
    return round(100_000 / pace_s_per_km)


def seconds_for(metres: float, pace_s_per_km: float, step: int) -> int:
    return max(step, round(metres * pace_s_per_km / 1000 / step) * step)


def _pair(heart_rate: HR | None) -> tuple[int, int] | None:
    if heart_rate is None or isinstance(heart_rate, tuple):
        return heart_rate
    return heart_rate, heart_rate


def steady(
    seconds: int,
    pace: float,
    heart_rate: HR,
    rng: random.Random,
    step: int = 1,
    hills: tuple[int, int] = (400, 1200),
    chunk: int = 300,
    lap: bool = False,
    power: int | None = None,
    cadence: int | None = None,
    dynamics: tuple[int, int, int] | None = None,
) -> list[Segment]:
    low, high = _pair(heart_rate) or (0, 0)
    count = max(1, seconds // chunk)
    lengths = [seconds // count // step * step] * count
    lengths[-1] += seconds - sum(lengths)
    out: list[Segment] = []
    elapsed = 0
    for index, length in enumerate(lengths):
        start_hr = round(low + (high - low) * elapsed / seconds)
        elapsed += length
        end_hr = round(low + (high - low) * elapsed / seconds)
        rise = 0
        if hills[1]:
            rise = rng.randrange(hills[0], hills[1] + 1, 20) * (1 if index % 2 == 0 else -1)
        out.append(
            Segment(
                length,
                speed(pace),
                (start_hr, end_hr),
                rise,
                lap=lap,
                cadence=cadence,
                power=power,
                dynamics=dynamics,
            )
        )
    return out


def route(rng: random.Random, metres: float, leg_m: float = 400.0) -> Route:
    bearing = rng.uniform(0, 360)
    legs = []
    for _ in range(int(metres // leg_m) + 1):
        legs.append((bearing % 360, leg_m))
        bearing += rng.uniform(-40, 40)
    latitude = HOME[0] + rng.uniform(-0.02, 0.02)
    longitude = HOME[1] + rng.uniform(-0.03, 0.03)
    return Route(latitude, longitude, tuple(legs))


def local(day: dt.date, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZONE).astimezone(dt.UTC)


def outdoor(
    slug: str,
    name: str,
    start: dt.datetime,
    segments: list[Segment],
    rng: random.Random,
    step: int = 1,
    noise: float = 2.5,
    sport: DemoSport = "running",
    flaws: tuple[str, ...] = (),
    formats: tuple[Format, ...] = ("fit",),
    leg_m: float = 400.0,
) -> Run:
    metres = sum(s.speed_cm_s * s.seconds + s.jump_cm for s in segments if not s.paused) / 100
    return Run(
        slug=slug,
        name=name,
        sport=sport,
        start=start,
        segments=tuple(segments),
        route=route(rng, metres, leg_m),
        altitude_cm=rng.randrange(400, 3000, 20),
        step_s=step,
        gps_noise_m=noise,
        formats=formats,
        flaws=flaws,
    )


def showcase(end: dt.date, rng: random.Random) -> list[Run]:
    def day(back: int) -> dt.date:
        return end - dt.timedelta(days=back)

    reps: list[Segment] = [*steady(900, 340, (128, 148), rng, chunk=900, lap=True)]
    for _ in range(6):
        reps.append(Segment(168, speed(210), (160, 176), lap=True))
        reps.append(Segment(90, speed(400), (176, 150), lap=True))
    reps.append(Segment(600, speed(350), (150, 140), rise_cm=-600, lap=True))
    stops = [
        *steady(600, 330, 141, rng),
        Segment(20, 0, (141, 128)),
        *steady(420, 330, (130, 143), rng),
        Segment(95, paused=True, heart_rate=(143, 118)),
        *steady(540, 325, (122, 144), rng),
        Segment(25, 0, (144, 130)),
        *steady(480, 330, (132, 143), rng),
        Segment(120, paused=True, heart_rate=(143, 115)),
        *steady(600, 330, (120, 142), rng),
    ]
    dropout = [
        *steady(900, 320, 146, rng),
        Segment(240, speed(320), None, rise_cm=400),
        *steady(600, 320, 147, rng, hills=(400, 400)),
        Segment(2, speed(320), (147, 147), jump_cm=9000),
        *steady(900, 320, (147, 150), rng),
    ]
    dynamics = steady(2700, 300, (148, 158), rng, power=262, cadence=176, dynamics=(238, 84, 1140))
    treadmill = Run(
        slug="treadmill",
        name="Treadmill run",
        sport="treadmill_running",
        start=local(day(9), 18, 30),
        segments=(
            Segment(600, speed(360), (120, 138), cadence=166),
            Segment(1800, speed(300), (140, 152), cadence=174),
            Segment(300, speed(380), (152, 135), cadence=164),
        ),
    )
    strapless = [
        Segment(1200, speed(335), None, rise_cm=800, cadence=172),
        Segment(1200, speed(335), None, rise_cm=-800, cadence=172),
    ]
    return [
        outdoor("easy", "Easy run", local(day(1), 7), steady(2880, 345, 142, rng), rng),
        outdoor(
            "no-heart-rate",
            "Run without a heart-rate strap",
            local(day(3), 12, 10),
            strapless,
            rng,
            flaws=("no heart rate anywhere: TRIMP and zones have nothing to work from",),
        ),
        outdoor("intervals-6x800", "6 x 800 m", local(day(2), 17, 45), reps, rng),
        outdoor(
            "long-run",
            "Long run with heart-rate drift",
            local(day(4), 8),
            steady(10800, 320, (138, 157), rng, chunk=600),
            rng,
            flaws=("heart rate drifts from 138 to 157 bpm at a steady 5:21 /km",),
        ),
        outdoor(
            "city-stops",
            "City run with stops",
            local(day(6), 7, 15),
            stops,
            rng,
            flaws=(
                "standing still 0:10:00-0:10:20 and 0:27:55-0:28:20, recorded",
                "auto-paused 0:17:20-0:18:55 and 0:36:20-0:38:20, nothing recorded",
            ),
        ),
        outdoor(
            "dropout-and-jump",
            "Strap dropout and GPS jump",
            local(day(8), 6, 50),
            dropout,
            rng,
            flaws=(
                "no heart rate 0:15:00-0:19:00",
                "GPS jump of 90 m at 0:29:00-0:29:02, a pace spike",
            ),
        ),
        treadmill,
        outdoor(
            "ride",
            "Ride",
            local(day(10), 9),
            steady(5400, 122, (128, 146), rng, hills=(1000, 6000), power=205, cadence=88),
            rng,
            sport="cycling",
        ),
        outdoor(
            "power-dynamics",
            "Run with power and running dynamics",
            local(day(12), 7),
            dynamics,
            rng,
        ),
        outdoor(
            "three-formats",
            "Same run in three formats",
            local(day(13), 7, 30),
            steady(3125, 312.5, 144, rng, hills=(0, 0), chunk=3125),
            rng,
            noise=0.0,
            formats=("fit", "gpx", "tcx"),
            flaws=(
                "imported as FIT, GPX and TCX, so this day counts three times in training load",
                "the GPX copy has no laps, speed or distance; its distance comes from positions",
            ),
            leg_m=1600.0,
        ),
    ]


def _workout(kind: int, fitness: float, rng: random.Random) -> tuple[str, str, list[Segment]]:
    step = 5
    warm = steady(900, 350 * fitness, (125, 140), rng, step)
    cool = steady(600, 360 * fitness, (150, 138), rng, step)
    work: list[Segment] = []
    if kind == 0:
        for _ in range(3):
            work.append(Segment(600, speed(265 * fitness), (158, 168)))
            work.append(Segment(120, speed(380 * fitness), (168, 148)))
        return "tempo", "Tempo 3 x 10 min", warm + work + cool
    if kind == 1:
        for _ in range(5):
            pace = 228 * fitness
            work.append(Segment(seconds_for(1000, pace, step), speed(pace), (164, 178)))
            work.append(Segment(90, speed(400 * fitness), (178, 150)))
        return "reps-5x1k", "5 x 1 km", warm + work + cool
    pace = 236 * fitness
    work.append(Segment(seconds_for(5000, pace, step), speed(pace), (168, 184)))
    return "time-trial-5k", "5 km time trial", warm + work + cool


def history(end: dt.date, rng: random.Random) -> list[Run]:
    runs: list[Run] = []
    for back in range(HISTORY_DAYS, SHOWCASE_DAYS, -1):
        day = end - dt.timedelta(days=back)
        if INJURY[1] <= back <= INJURY[0]:
            continue
        fitness = 1.05 - 0.05 * (HISTORY_DAYS - back) / HISTORY_DAYS
        taper = 0.6 if RACE_DAY < back <= RACE_DAY + 14 else 1.0
        weekday = day.weekday()
        if back == RACE_DAY:
            pace = 275 * fitness
            segments = steady(600, 380, (120, 140), rng, 5) + steady(
                seconds_for(21097.5, pace, 5), pace, (165, 180), rng, 5, chunk=600
            )
            runs.append(
                outdoor("half-marathon", "Half marathon race", local(day, 9), segments, rng, 5)
            )
        elif weekday == 1:
            minutes = rng.randrange(40, 56) * taper
            segments = steady(int(minutes) * 60, 345 * fitness, (136, 144), rng, 5)
            runs.append(outdoor("easy", "Easy run", local(day, 7), segments, rng, 5))
        elif weekday == 3:
            slug, name, segments = _workout(day.isocalendar().week % 3, fitness, rng)
            runs.append(outdoor(slug, name, local(day, 17, 30), segments, rng, 5))
        elif weekday == 5:
            minutes = rng.randrange(75, 111) * taper
            segments = steady(int(minutes) * 60, 330 * fitness, (138, 152), rng, 5, chunk=600)
            runs.append(outdoor("long-run", "Long run", local(day, 8, 30), segments, rng, 5))
        elif weekday == 6 and rng.random() < 0.5:
            minutes = rng.randrange(30, 41)
            segments = steady(minutes * 60, 355 * fitness, (132, 140), rng, 5)
            runs.append(outdoor("recovery", "Recovery run", local(day, 10), segments, rng, 5))
    return runs


def catalogue(end: dt.date, rng: random.Random) -> list[Run]:
    return history(end, rng) + showcase(end, rng)

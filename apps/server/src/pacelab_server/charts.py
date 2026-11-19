import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl

from pacelab_server.training import Day

WIDTH = 720
HEIGHT = 160
INSET = 12
MAX_POINTS = 600
MIN_LOAD_TOP = 10.0
MIN_FORM_SPAN = 5.0


@dataclass(frozen=True, slots=True)
class Series:
    path: str
    low: float
    high: float


def series(records: pl.DataFrame, column: str, invert: bool = False) -> Series | None:
    if column == "pace":
        frame = records.filter(pl.col("speed") > 0.5).select(
            "distance", pace=1000 / pl.col("speed")
        )
    else:
        frame = records.select("distance", column).drop_nulls()
    if frame.height < 2:
        return None
    step = max(1, frame.height // MAX_POINTS)
    frame = frame.gather_every(step)
    x = frame["distance"].to_list()
    y = frame[column].to_list()
    x0, x1 = x[0], x[-1]
    low, high = min(y), max(y)
    span_x = (x1 - x0) or 1.0
    span_y = (high - low) or 1.0
    points = []
    for xi, yi in zip(x, y, strict=True):
        fraction = (yi - low) / span_y
        top = fraction if invert else 1 - fraction
        y_px = INSET + top * (HEIGHT - 2 * INSET)
        points.append(f"{(xi - x0) / span_x * WIDTH:.1f},{y_px:.1f}")
    return Series(path="M" + " L".join(points), low=low, high=high)


@dataclass(frozen=True, slots=True)
class ZoneBar:
    name: str
    bpm: str
    seconds: float
    share: float


def zone_bars(seconds: Sequence[float], boundaries_bpm: Sequence[float]) -> list[ZoneBar]:
    total = sum(seconds)
    if not total:
        return []
    starts = [math.ceil(boundary) for boundary in boundaries_bpm]
    bars = []
    for zone, zone_seconds in enumerate(seconds):
        if zone == 0:
            bpm = f"under {starts[0]} bpm"
        elif zone == len(starts):
            bpm = f"{starts[-1]} bpm and up"
        else:
            bpm = f"{starts[zone - 1]}-{starts[zone] - 1} bpm"
        bars.append(ZoneBar(f"Zone {zone + 1}", bpm, zone_seconds, zone_seconds / total))
    return bars


@dataclass(frozen=True, slots=True)
class Hit:
    x: float
    width: float
    title: str


@dataclass(frozen=True, slots=True)
class Line:
    path: str
    end: float


LABEL_GAP = 12.0


def spread_labels(ends: dict[str, float]) -> list[tuple[str, float]]:
    placed: list[tuple[str, float]] = []
    for name, top in sorted(ends.items(), key=lambda item: item[1]):
        top = max(top, placed[-1][1] + LABEL_GAP if placed else LABEL_GAP)
        placed.append((name, top))
    overflow = placed[-1][1] - 100.0 if placed else 0.0
    if overflow > 0:
        placed = [(name, top - overflow) for name, top in placed]
    return placed


@dataclass(frozen=True, slots=True)
class LoadChart:
    fitness: Line
    fatigue: Line
    form: Line
    load_top: float
    form_low: float
    form_high: float
    zero: float
    hits: list[Hit]

    @property
    def end_labels(self) -> list[tuple[str, float]]:
        return spread_labels({"Fitness": self.fitness.end, "Fatigue": self.fatigue.end})


def load_chart(days: Sequence[Day]) -> LoadChart:
    last = len(days) - 1
    indices = list(range(0, len(days), max(1, len(days) // MAX_POINTS)))
    if indices[-1] != last:
        indices.append(last)
    sampled = [days[index] for index in indices]
    xs = [index / last * WIDTH for index in indices] if last else [WIDTH / 2]
    load_top = max(MIN_LOAD_TOP, *(max(day.fitness, day.fatigue) for day in days))
    form_low = min(-MIN_FORM_SPAN, *(day.form for day in days))
    form_high = max(MIN_FORM_SPAN, *(day.form for day in days))

    def y(value: float, low: float, high: float) -> float:
        fraction = (value - low) / ((high - low) or 1.0)
        return INSET + (1 - fraction) * (HEIGHT - 2 * INSET)

    def line(key: str, low: float, high: float) -> Line:
        values = [getattr(day, key) for day in sampled]
        points = [f"{x:.1f},{y(v, low, high):.1f}" for x, v in zip(xs, values, strict=True)]
        if len(points) == 1:
            points = [f"0,{y(values[0], low, high):.1f}", f"{WIDTH},{y(values[0], low, high):.1f}"]
        return Line(path="M" + " L".join(points), end=y(values[-1], low, high) / HEIGHT * 100)

    edges = [0.0, *((a + b) / 2 for a, b in itertools.pairwise(xs)), float(WIDTH)]
    hits = [
        Hit(
            x=edges[position],
            width=edges[position + 1] - edges[position],
            title=(
                f"{day.date:%Y-%m-%d}: fitness {day.fitness:.0f}, fatigue {day.fatigue:.0f}, "
                f"form {round(day.form):+d}, TRIMP {day.load:.0f}"
            ),
        )
        for position, day in enumerate(sampled)
    ]
    return LoadChart(
        fitness=line("fitness", 0.0, load_top),
        fatigue=line("fatigue", 0.0, load_top),
        form=line("form", form_low, form_high),
        load_top=load_top,
        form_low=form_low,
        form_high=form_high,
        zero=y(0.0, form_low, form_high),
        hits=hits,
    )

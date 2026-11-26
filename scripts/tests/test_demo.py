import datetime as dt
from pathlib import Path

import pytest
from demo import fill
from demo_runs import Route, Run, Segment
from fastapi.testclient import TestClient
from makerundev_server import create_app

RUN = Run(
    slug="hand-checked",
    name="Hand-checked run",
    sport="running",
    start=dt.datetime(2026, 3, 1, 7, 0, tzinfo=dt.UTC),
    route=Route(55.67, 12.56, legs=((0.0, 5000.0),)),
    altitude_cm=1000,
    segments=(
        Segment(600, 300, heart_rate=(150, 150), rise_cm=1000),
        Segment(20, 0, heart_rate=(150, 150)),
        Segment(600, 250, heart_rate=(160, 160), rise_cm=-1000),
    ),
)

HAND_COMPUTED = {
    "distance_m": 3300.0,
    "elapsed_s": 1220.0,
    "moving_s": 1200.0,
    "pace_s_per_km": 1200 / 3.3,
    "avg_heart_rate_bpm": 155.0,
    "max_heart_rate_bpm": 160.0,
    "elevation_gain_m": 10.0,
}
HAND_SPLITS = [
    *(1000.0, 1000 / 3, 1000 / 3),
    *(1000.0, 800 / 3 + 20 + 80, 800 / 3 + 80),
    *(1000.0, 400.0, 400.0),
    *(300.0, 120.0, 120.0),
]


def figures(source: dict[str, object]) -> dict[str, object]:
    return {key: source[key] for key in HAND_COMPUTED}


def splits(source: list[dict[str, float]]) -> list[float]:
    return [split[key] for split in source for key in ("distance_m", "elapsed_s", "moving_s")]


def test_a_demo_run_shows_the_figures_it_was_built_with(tmp_path: Path) -> None:
    (entry,) = fill(tmp_path, [RUN])
    detail = TestClient(create_app(data_dir=tmp_path)).get(
        f"/api/activities/{entry['activity_id']}"
    )

    expected = pytest.approx(HAND_COMPUTED, abs=0.05)
    assert figures(entry["expected"]) == expected
    assert figures(detail.json()) == expected
    assert splits(entry["expected"]["splits"]) == pytest.approx(HAND_SPLITS, abs=0.05)
    assert splits(detail.json()["splits"]) == pytest.approx(HAND_SPLITS, abs=0.05)

import argparse
import datetime as dt
import json
import random
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from demo_files import Point, fit, gpx, speeds, tcx, track
from demo_plan import ZONE, catalogue
from demo_runs import Run, Sample, expected, samples
from fastapi.testclient import TestClient
from makerundev_server import create_app
from makerundev_server.config import database_path

SEED = 2026
SETTINGS = {
    "max_heart_rate_bpm": 190,
    "resting_heart_rate_bpm": 48,
    "trimp_coefficients": "male",
    "zone_model": "max_hr_percent",
    "zone_thresholds_percent": [60, 70, 80, 90],
    "body_mass_kg": 68,
    "timezone": ZONE.key,
}
TOLERANCE = {
    "distance_m": "1 cm for FIT and TCX; GPX has no distance, so about 1 m from its positions",
    "splits": "a GPX copy can end in an extra split of under a metre",
    "times_s": "0.01 s",
    "avg_heart_rate_bpm": "0.5 bpm: each recording interval takes the heart rate at its start",
}


def write(fmt: str, run: Run, rows: list[Sample], points: list[Point], speed: list[float]) -> bytes:
    if fmt == "gpx":
        return gpx(run, rows, points)
    if fmt == "tcx":
        return tcx(run, rows, points, speed)
    return fit(run, rows, points, speed)


def fill(data_dir: Path, runs: Sequence[Run], seed: int = SEED) -> list[dict[str, Any]]:
    if database_path(data_dir).exists():
        raise SystemExit(f"{data_dir} already holds a makerundev database; pick an empty directory")
    folder = data_dir / "demo"
    folder.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    client = TestClient(create_app(data_dir=data_dir))
    saved = client.put("/api/settings", json=SETTINGS)
    if saved.status_code != 200:
        raise SystemExit(f"settings were refused: {saved.text}")
    entries: list[dict[str, Any]] = []
    for run in runs:
        rows = samples(run, rng)
        points = track(run, rows, rng)
        speed = speeds(rows, rng)
        figures = expected(run)
        for fmt in run.formats:
            filename = f"{run.start:%Y-%m-%d}-{run.slug}.{fmt}"
            data = write(fmt, run, rows, points, speed)
            (folder / filename).write_bytes(data)
            response = client.post(
                "/api/activities", files=[("files", (filename, data, "application/octet-stream"))]
            )
            (result,) = response.json()["results"]
            if result["status"] != "imported":
                raise SystemExit(f"{filename} was not imported: {result}")
            entries.append(
                {
                    "activity_id": result["activity_id"],
                    "file": f"demo/{filename}",
                    "format": fmt,
                    "sport": run.sport,
                    "name": run.name,
                    "start_time": run.start.isoformat(),
                    "flaws": list(run.flaws),
                    "expected": figures if fmt != "gpx" else {**figures, "laps": []},
                }
            )
    return entries


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fill an empty data directory with demo runs.")
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--end", type=dt.date.fromisoformat, default=dt.date.today())
    args = parser.parse_args(argv)
    runs = catalogue(args.end, random.Random(args.seed))
    entries = fill(args.data_dir, runs, args.seed)
    manifest = {
        "seed": args.seed,
        "end": args.end.isoformat(),
        "settings": SETTINGS,
        "tolerance": TOLERANCE,
        "activities": entries,
    }
    path = args.data_dir / "demo" / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"{len(entries)} demo activities imported into {args.data_dir}; expected figures in {path}"
    )


if __name__ == "__main__":
    main(sys.argv[1:])

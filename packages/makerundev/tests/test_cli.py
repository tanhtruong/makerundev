import re
from pathlib import Path

import polars as pl
import pytest
from makerundev.cli import app
from makerundev.io import load
from makerundev.model import STREAM_SCHEMA
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def default_units(monkeypatch):
    monkeypatch.delenv("MAKERUNDEV_UNITS", raising=False)


def test_splits_prints_each_kilometre_with_its_moving_time_and_pace(tmp_path, make_fit):
    path = tmp_path / "run.fit"
    path.write_bytes(make_fit([{"t": float(i), "distance": i * 4.0} for i in range(626)]))

    result = CliRunner().invoke(app, ["splits", str(path)])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        " 1  1.00 km  4:10  4:10 /km",
        " 2  1.00 km  4:10  4:10 /km",
        " 3  0.50 km  2:05  4:10 /km",
    ]


def test_splits_in_miles_prints_each_mile_with_its_pace_per_mile(tmp_path, make_fit):
    path = tmp_path / "run.fit"
    path.write_bytes(make_fit([{"t": float(i), "distance": i * 4.0} for i in range(926)]))

    result = CliRunner().invoke(app, ["splits", "--units", "mi", str(path)])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        " 1  1.00 mi  6:42  6:42 /mi",
        " 2  1.00 mi  6:42  6:42 /mi",
        " 3  0.30 mi  2:00  6:42 /mi",
    ]


def test_zones_prints_the_time_and_share_of_heart_rate_time_in_each_zone(tmp_path, make_fit):
    path = tmp_path / "run.fit"
    rows = [
        {"t": float(t), "distance": t * 3.0, "hr": 100 if t < 60 else 150 if t < 180 else 185}
        for t in range(301)
    ]
    path.write_bytes(make_fit(rows))

    result = CliRunner().invoke(app, ["zones", str(path), "--max-hr", "200"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "Zone 1  under 120 bpm   1:00  20%",
        "Zone 2  120-139 bpm     0:00   0%",
        "Zone 3  140-159 bpm     2:00  40%",
        "Zone 4  160-179 bpm     0:00   0%",
        "Zone 5  180 bpm and up  2:00  40%",
    ]


def test_zones_with_the_reserve_model_start_at_resting_plus_a_share_of_the_reserve(
    tmp_path, make_fit
):
    path = tmp_path / "run.fit"
    path.write_bytes(make_fit([{"t": float(t), "distance": t * 3.0, "hr": 150} for t in range(61)]))

    result = CliRunner().invoke(
        app,
        ["zones", str(path), "--max-hr", "200", "--resting-hr", "50", "--model", "reserve"],
    )

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "Zone 1  under 140 bpm   0:00    0%",
        "Zone 2  140-154 bpm     1:00  100%",
        "Zone 3  155-169 bpm     0:00    0%",
        "Zone 4  170-184 bpm     0:00    0%",
        "Zone 5  185 bpm and up  0:00    0%",
    ]


@pytest.mark.parametrize(
    ("arguments", "reason"),
    [
        ([], "must be given with --model reserve"),
        (["--resting-hr", "200"], "must be below --max-hr"),
    ],
)
def test_zones_with_the_reserve_model_refuse_a_missing_or_too_high_resting_heart_rate(
    tmp_path, make_fit, arguments, reason
):
    path = tmp_path / "run.fit"
    path.write_bytes(make_fit([{"t": float(t), "hr": 150} for t in range(60)]))

    result = CliRunner().invoke(
        app, ["zones", str(path), "--max-hr", "190", "--model", "reserve", *arguments]
    )

    error = re.sub(r"\x1b\[[0-9;]*m", "", result.stderr)
    assert result.exit_code == 2
    assert "--resting-hr" in error
    assert reason in error


def test_trimp_prints_the_banister_score_as_a_whole_number(tmp_path, make_fit):
    path = tmp_path / "run.fit"
    rows = [{"t": t * 2.0, "distance": t * 6.0, "hr": 120} for t in range(1801)]
    path.write_bytes(make_fit(rows))

    result = CliRunner().invoke(app, ["trimp", str(path), "--max-hr", "190", "--resting-hr", "50"])

    assert result.exit_code == 0
    assert result.output == "50\n"


@pytest.mark.parametrize(
    "arguments",
    [["zones", "--max-hr", "190"], ["trimp", "--max-hr", "190", "--resting-hr", "50"]],
)
def test_heart_rate_commands_fail_on_a_file_without_heart_rate(tmp_path, make_fit, arguments):
    path = tmp_path / "run.fit"
    path.write_bytes(make_fit([{"t": float(t), "distance": t * 3.0} for t in range(60)]))

    result = CliRunner().invoke(app, [arguments[0], str(path), *arguments[1:]])

    assert result.exit_code == 1
    assert result.stderr == f"{path}: no heart rate data\n"


def test_zones_rejects_thresholds_that_do_not_ascend(tmp_path, make_fit):
    path = tmp_path / "run.fit"
    path.write_bytes(make_fit([{"t": float(t), "hr": 150} for t in range(60)]))

    result = CliRunner().invoke(
        app, ["zones", str(path), "--max-hr", "190", "--thresholds", "60,80,70,90"]
    )

    assert result.exit_code == 2
    assert "ascending" in result.stderr


def test_laps_prints_each_recorded_lap_with_its_distance_time_and_pace(tmp_path, make_fit):
    path = tmp_path / "run.fit"
    laps = [
        {"t": 0.0, "elapsed": 330.0, "distance": 1000.0},
        {"t": 330.0, "elapsed": 270.0, "distance": 800.0},
        {"t": 600.0, "elapsed": 30.0},
    ]
    path.write_bytes(
        make_fit([{"t": float(i), "distance": i * 3.0} for i in range(631)], laps=laps)
    )

    result = CliRunner().invoke(app, ["laps", str(path)])
    miles = CliRunner().invoke(app, ["laps", "--units", "mi", str(path)])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        " 1  1.00 km  5:30  5:30 /km",
        " 2  0.80 km  4:30  5:38 /km",
        " 3        -  0:30  -",
    ]
    assert miles.output.splitlines() == [
        " 1  0.62 mi  5:30  8:51 /mi",
        " 2  0.50 mi  4:30  9:03 /mi",
        " 3        -  0:30  -",
    ]


def test_summary_prints_each_readable_file_and_long_adds_gap_decoupling_and_estimated_power(
    tmp_path, make_fit
):
    hill = tmp_path / "hill.fit"
    hill.write_bytes(
        make_fit(
            [
                {
                    "t": i * 3.0,
                    "distance": i * 10.0,
                    "altitude": 200 + i * 1.0,
                    "hr": 140 if i < 150 else 147,
                }
                for i in range(301)
            ]
        )
    )
    bare = tmp_path / "bare.fit"
    bare.write_bytes(make_fit([{"t": float(i), "distance": i * 4.0} for i in range(626)]))
    broken = tmp_path / "broken.fit"
    broken.write_bytes(b"not an activity")

    long = CliRunner().invoke(app, ["summary", "--long", str(hill), str(bare)])
    default = CliRunner().invoke(app, ["summary", str(broken), str(hill)])
    miles = CliRunner().invoke(app, ["summary", "--long", "--units", "mi", str(hill)])
    power = CliRunner().invoke(
        app, ["summary", "--long", "--body-mass", "70", str(hill), str(bare)]
    )
    without_long = CliRunner().invoke(app, ["summary", "--body-mass", "70", str(hill)])

    assert long.exit_code == 0
    assert long.output.splitlines() == [
        "hill.fit  2026-03-01 07:00  running  3.00 km  15:00  5:00 /km  144 bpm  +300 m"
        "  GAP 3:01 /km  decoupling +4.8%",
        "bare.fit  2026-03-01 07:00  running  2.50 km  10:25  4:10 /km  -  +0 m"
        "  GAP -  decoupling -",
    ]
    assert default.exit_code == 1
    assert default.stdout.splitlines() == [
        "hill.fit  2026-03-01 07:00  running  3.00 km  15:00  5:00 /km  144 bpm  +300 m",
    ]
    assert default.stderr == f"{broken}: unsupported file: expected FIT, GPX or TCX\n"
    assert miles.output.splitlines() == [
        "hill.fit  2026-03-01 07:00  running  1.86 mi  15:00  8:03 /mi  144 bpm  +300 m"
        "  GAP 4:51 /mi  decoupling +4.8%",
    ]
    assert power.exit_code == 0
    assert power.output.splitlines() == [
        "hill.fit  2026-03-01 07:00  running  3.00 km  15:00  5:00 /km  144 bpm  +300 m"
        "  GAP 3:01 /km  decoupling +4.8%  est. power 365 W",
        "bare.fit  2026-03-01 07:00  running  2.50 km  10:25  4:10 /km  -  +0 m"
        "  GAP -  decoupling -  est. power -",
    ]
    assert without_long.exit_code == 2
    assert without_long.stdout == ""


def test_efforts_prints_the_fastest_time_over_each_distance_the_run_covers(tmp_path, make_fit):
    path = tmp_path / "run.fit"
    path.write_bytes(make_fit([{"t": float(i), "distance": i * 4.0} for i in range(801)]))

    result = CliRunner().invoke(app, ["efforts", str(path)])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "         400 m  1:40",
        "          1 km  4:10",
        "        1 mile  6:42",
        "          3 km  12:30",
    ]


@pytest.mark.parametrize(
    ("suffix", "read_back"),
    [
        (".csv", lambda path: pl.read_csv(path, schema=STREAM_SCHEMA)),
        (".parquet", pl.read_parquet),
    ],
)
def test_export_writes_the_record_stream_that_reads_back_unchanged(
    tmp_path, steady_run_fit, suffix, read_back
):
    path = tmp_path / "run.fit"
    path.write_bytes(steady_run_fit)
    output = tmp_path / f"run{suffix}"

    result = CliRunner().invoke(app, ["export", str(path), str(output)])

    assert result.exit_code == 0
    assert read_back(output).equals(load(path).records)


def test_export_rejects_an_output_that_is_not_csv_or_parquet(tmp_path, steady_run_fit):
    path = tmp_path / "run.fit"
    path.write_bytes(steady_run_fit)
    output = tmp_path / "run.json"

    result = CliRunner().invoke(app, ["export", str(path), str(output)])

    assert result.exit_code == 2
    assert ".csv or .parquet" in result.stderr
    assert not output.exists()


def test_anonymize_writes_a_shifted_copy_and_never_overwrites_a_file(tmp_path):
    source = Path(__file__).parent / "fixtures" / "run.gpx"
    output = tmp_path / "shifted.gpx"

    first = CliRunner().invoke(app, ["anonymize", str(source), str(output)])
    written = output.read_bytes()
    onto_itself = CliRunner().invoke(app, ["anonymize", str(output), str(output)])

    assert first.exit_code == 0
    assert first.output.split()[1] == "3"
    assert written != source.read_bytes()
    assert onto_itself.exit_code != 0
    assert output.read_bytes() == written

import pytest
from makerundev.cli import app
from typer.testing import CliRunner


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

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        " 1  1.00 km  5:30  5:30 /km",
        " 2  0.80 km  4:30  5:38 /km",
        " 3        -  0:30  -",
    ]


def test_summary_long_adds_grade_adjusted_pace_and_decoupling_to_each_line(tmp_path, make_fit):
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

    long = CliRunner().invoke(app, ["summary", "--long", str(hill), str(bare)])
    default = CliRunner().invoke(app, ["summary", str(hill)])

    assert long.exit_code == 0
    assert long.output.splitlines() == [
        "hill.fit  2026-03-01 07:00  running  3.00 km  15:00  5:00 /km  144 bpm  +300 m"
        "  GAP 3:01 /km  decoupling +4.8%",
        "bare.fit  2026-03-01 07:00  running  2.50 km  10:25  4:10 /km  -  +0 m"
        "  GAP -  decoupling -",
    ]
    assert default.output.splitlines() == [
        "hill.fit  2026-03-01 07:00  running  3.00 km  15:00  5:00 /km  144 bpm  +300 m",
    ]

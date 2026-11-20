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

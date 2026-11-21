import itertools
from pathlib import Path
from typing import Annotated

import typer

from makerundev import format
from makerundev.errors import ActivityFileError
from makerundev.io import load
from makerundev.metrics import (
    BANISTER_FEMALE,
    BANISTER_MALE,
    DEFAULT_ZONE_THRESHOLDS,
    best_efforts,
    splits,
    summarize,
    time_in_zones,
    trimp,
)
from makerundev.model import Activity

app = typer.Typer(no_args_is_help=True, help="Analyse FIT, GPX and TCX activity files.")

Files = Annotated[list[Path], typer.Argument(exists=True, dir_okay=False, readable=True)]
File = Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)]
MaxHr = Annotated[int, typer.Option("--max-hr", min=1, help="Max heart rate in bpm.")]
RestingHr = Annotated[int, typer.Option("--resting-hr", min=1, help="Resting heart rate in bpm.")]


@app.command(help="Print distance, time, pace, heart rate and climb for each file.")
def summary(files: Files) -> None:
    failed = False
    for path in files:
        try:
            activity = load(path)
        except ActivityFileError as error:
            typer.echo(f"{path}: {error}", err=True)
            failed = True
            continue
        result = summarize(activity)
        heart_rate = f"{result.avg_heart_rate:.0f} bpm" if result.avg_heart_rate else "-"
        typer.echo(
            f"{path.name}  {activity.start_time:%Y-%m-%d %H:%M}  {activity.sport.value}  "
            f"{format.kilometres(result.distance_m)}  {format.duration(result.moving_s)}  "
            f"{format.pace(result.pace_s_per_km)}  {heart_rate}  "
            f"+{result.elevation_gain_m:.0f} m"
        )
    if failed:
        raise typer.Exit(1)


@app.command(help="Print the fastest time over standard distances.")
def efforts(file: File) -> None:
    for distance, seconds in best_efforts(_load(file)).items():
        typer.echo(f"{format.distance_name(distance):>14}  {format.duration(seconds)}")


@app.command("splits", help="Print the moving time and pace of each kilometre.")
def splits_command(file: File) -> None:
    rows = [
        (
            format.kilometres(split.distance_m),
            format.duration(split.moving_s),
            format.pace(split.pace_s_per_km),
        )
        for split in splits(_load(file))
    ]
    width = max((len(time) for _, time, _ in rows), default=0)
    digits = max(2, len(str(len(rows))))
    for number, (distance, time, pace) in enumerate(rows, start=1):
        typer.echo(f"{number:>{digits}}  {distance}  {time:>{width}}  {pace}")


@app.command(help="Print the distance, time and pace of each lap the watch recorded.")
def laps(file: File) -> None:
    rows = [
        (
            format.kilometres(lap.distance_m) if lap.distance_m is not None else "-",
            format.duration(lap.elapsed_s) if lap.elapsed_s is not None else "-",
            format.pace(lap.pace_s_per_km),
        )
        for lap in _load(file).laps
    ]
    distance_width = max((len(distance) for distance, _, _ in rows), default=0)
    time_width = max((len(time) for _, time, _ in rows), default=0)
    digits = max(2, len(str(len(rows))))
    for number, (distance, time, pace) in enumerate(rows, start=1):
        typer.echo(
            f"{number:>{digits}}  {distance:>{distance_width}}  {time:>{time_width}}  {pace}"
        )


@app.command(help="Print the time spent in each heart-rate zone.")
def zones(
    file: File,
    max_hr: MaxHr,
    thresholds: Annotated[
        str,
        typer.Option(help="Zone thresholds as ascending percentages of max heart rate."),
    ] = ",".join(f"{threshold:g}" for threshold in DEFAULT_ZONE_THRESHOLDS),
) -> None:
    boundaries = [max_hr * threshold / 100 for threshold in _thresholds(thresholds)]
    seconds = time_in_zones(_load_heart_rate(file), boundaries)
    total = sum(seconds)
    rows = [
        (
            f"Zone {zone + 1}",
            format.zone_range(zone, boundaries),
            format.duration(time),
            f"{time / total * 100 if total else 0:.0f}%",
        )
        for zone, time in enumerate(seconds)
    ]
    widths = [max(len(row[column]) for row in rows) for column in range(4)]
    for name, bpm, time, share in rows:
        typer.echo(
            f"{name:<{widths[0]}}  {bpm:<{widths[1]}}  {time:>{widths[2]}}  {share:>{widths[3]}}"
        )


@app.command("trimp", help="Print the Banister TRIMP training load as a whole number.")
def trimp_command(
    file: File,
    max_hr: MaxHr,
    resting_hr: RestingHr,
    female: Annotated[bool, typer.Option(help="Use the female Banister coefficients.")] = False,
) -> None:
    if resting_hr >= max_hr:
        raise typer.BadParameter("must be below --max-hr", param_hint="--resting-hr")
    coefficients = BANISTER_FEMALE if female else BANISTER_MALE
    typer.echo(f"{trimp(_load_heart_rate(file), resting_hr, max_hr, coefficients):.0f}")


@app.command(help="Write the normalised record stream to .csv or .parquet.")
def export(file: File, output: Annotated[Path, typer.Argument(dir_okay=False)]) -> None:
    records = _load(file).records
    if output.suffix == ".parquet":
        records.write_parquet(output)
    elif output.suffix == ".csv":
        records.write_csv(output)
    else:
        raise typer.BadParameter("output must end in .csv or .parquet", param_hint="OUTPUT")


def _load(path: Path) -> Activity:
    try:
        return load(path)
    except ActivityFileError as error:
        typer.echo(f"{path}: {error}", err=True)
        raise typer.Exit(1) from error


def _load_heart_rate(path: Path) -> Activity:
    activity = _load(path)
    if activity.records["heart_rate"].is_null().all():
        typer.echo(f"{path}: no heart rate data", err=True)
        raise typer.Exit(1)
    return activity


def _thresholds(value: str) -> list[float]:
    try:
        thresholds = [float(part) for part in value.split(",")]
    except ValueError as error:
        raise typer.BadParameter(
            "must be comma-separated numbers", param_hint="--thresholds"
        ) from error
    if not all(0 < threshold < 100 for threshold in thresholds):
        raise typer.BadParameter("each must be above 0 and below 100", param_hint="--thresholds")
    if any(low >= high for low, high in itertools.pairwise(thresholds)):
        raise typer.BadParameter("must be strictly ascending", param_hint="--thresholds")
    return thresholds

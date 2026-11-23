import itertools
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from makerundev import format
from makerundev.errors import ActivityFileError
from makerundev.io import anonymize, load
from makerundev.metrics import (
    BANISTER_FEMALE,
    BANISTER_MALE,
    BODY_MASS_RANGE_KG,
    DEFAULT_ZONE_THRESHOLDS,
    aerobic_decoupling,
    best_efforts,
    estimated_power,
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


Units = Annotated[
    format.Unit,
    typer.Option(envvar="MAKERUNDEV_UNITS", help="Print distance and pace in km or mi."),
]
Long = Annotated[
    bool,
    typer.Option(
        "--long",
        "-l",
        help="Also print grade-adjusted pace, aerobic decoupling and, "
        "with --body-mass, estimated power.",
    ),
]
BodyMass = Annotated[
    float | None,
    typer.Option(
        "--body-mass",
        min=BODY_MASS_RANGE_KG[0],
        max=BODY_MASS_RANGE_KG[1],
        metavar="KG",
        help="Body mass in kg, for estimated power with --long.",
    ),
]


@app.command(
    help="Print distance, time, pace, heart rate and climb for each file, "
    "and with --long grade-adjusted pace, aerobic decoupling and, given --body-mass, "
    "estimated power."
)
def summary(
    files: Files,
    long: Long = False,
    body_mass: BodyMass = None,
    units: Units = format.Unit.KM,
) -> None:
    if body_mass is not None and not long:
        raise typer.BadParameter("needs --long", param_hint="--body-mass")
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
        line = (
            f"{path.name}  {activity.start_time:%Y-%m-%d %H:%M}  {activity.sport.value}  "
            f"{format.distance(result.distance_m, units)}  {format.duration(result.moving_s)}  "
            f"{format.pace(result.pace_s_per_km, units)}  {heart_rate}  "
            f"+{result.elevation_gain_m:.0f} m"
        )
        if long:
            line += (
                f"  GAP {format.pace(result.grade_adjusted_pace_s_per_km, units)}"
                f"  decoupling {format.decoupling(aerobic_decoupling(activity))}"
            )
            if body_mass is not None:
                line += f"  est. power {format.power(estimated_power(activity, body_mass))}"
        typer.echo(line)
    if failed:
        raise typer.Exit(1)


@app.command(help="Print the fastest time over standard distances.")
def efforts(file: File) -> None:
    for distance, seconds in best_efforts(_load(file)).items():
        typer.echo(f"{format.distance_name(distance):>14}  {format.duration(seconds)}")


@app.command("splits", help="Print the moving time and pace of each kilometre or mile.")
def splits_command(file: File, units: Units = format.Unit.KM) -> None:
    rows = [
        (
            format.distance(split.distance_m, units),
            format.duration(split.moving_s),
            format.pace(split.pace_s_per_km, units),
        )
        for split in splits(_load(file), every_m=units.metres)
    ]
    width = max((len(time) for _, time, _ in rows), default=0)
    digits = max(2, len(str(len(rows))))
    for number, (distance, time, pace) in enumerate(rows, start=1):
        typer.echo(f"{number:>{digits}}  {distance}  {time:>{width}}  {pace}")


@app.command(help="Print the distance, time and pace of each lap the watch recorded.")
def laps(file: File, units: Units = format.Unit.KM) -> None:
    rows = [
        (
            format.distance(lap.distance_m, units) if lap.distance_m is not None else "-",
            format.duration(lap.elapsed_s) if lap.elapsed_s is not None else "-",
            format.pace(lap.pace_s_per_km, units),
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


@app.command(
    "anonymize",
    help="Write a copy with every position moved far away, safe to attach to a bug report.",
)
def anonymize_command(file: File, output: Annotated[Path, typer.Argument(dir_okay=False)]) -> None:
    try:
        result = anonymize(file.read_bytes())
    except ActivityFileError as error:
        _fail(file, error)
    try:
        with output.open("xb") as target:
            target.write(result.data)
    except FileExistsError as error:
        raise typer.BadParameter("already exists", param_hint="OUTPUT") from error
    typer.echo(f"Shifted {result.positions} positions to {output}")
    if result.identifying:
        typer.echo(
            f"Still in the file: {', '.join(result.identifying)}. Check them before attaching it."
        )


def _load(path: Path) -> Activity:
    try:
        return load(path)
    except ActivityFileError as error:
        _fail(path, error)


def _fail(path: Path, error: ActivityFileError) -> NoReturn:
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

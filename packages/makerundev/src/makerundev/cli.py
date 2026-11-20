from pathlib import Path
from typing import Annotated

import typer

from makerundev import format
from makerundev.errors import ActivityFileError
from makerundev.io import load
from makerundev.metrics import best_efforts, summarize
from makerundev.model import Activity

app = typer.Typer(no_args_is_help=True, help="Analyse FIT, GPX and TCX activity files.")

Files = Annotated[list[Path], typer.Argument(exists=True, dir_okay=False, readable=True)]
File = Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)]


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

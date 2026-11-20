import datetime as dt
from collections.abc import Callable, Sequence
from typing import Any

import pytest
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import FileType, Manufacturer, Sport, SubSport

FIT_START = dt.datetime(2026, 3, 1, 7, 0, tzinfo=dt.UTC)

FitRow = dict[str, float]
MakeFit = Callable[..., bytes]


def _millis(seconds: float) -> int:
    return round((FIT_START.timestamp() + seconds) * 1000)


def build_fit(
    rows: Sequence[FitRow],
    sport: Any = Sport.RUNNING,
    sub_sport: Any = SubSport.GENERIC,
    laps: Sequence[FitRow] = (),
) -> bytes:
    builder = FitFileBuilder(auto_define=True, min_string_size=50)
    file_id = FileIdMessage()
    file_id.type = FileType.ACTIVITY
    file_id.manufacturer = Manufacturer.GARMIN.value
    file_id.product = 4315
    file_id.time_created = _millis(0)
    file_id.serial_number = 1
    builder.add(file_id)
    fields = {
        "lat": "position_lat",
        "lon": "position_long",
        "distance": "distance",
        "speed": "enhanced_speed",
        "altitude": "enhanced_altitude",
        "hr": "heart_rate",
        "cadence": "cadence",
        "power": "power",
        "stance_time": "stance_time",
        "vertical_oscillation": "vertical_oscillation",
        "step_length": "step_length",
    }
    for row in rows:
        record = RecordMessage()
        record.timestamp = _millis(row["t"])
        for key, attribute in fields.items():
            if key in row:
                setattr(record, attribute, row[key])
        builder.add(record)
    for row in laps:
        lap = LapMessage()
        if "t" in row:
            lap.start_time = _millis(row["t"])
            lap.timestamp = _millis(row["t"] + row.get("elapsed", 0.0))
        if "elapsed" in row:
            lap.total_elapsed_time = row["elapsed"]
        if "distance" in row:
            lap.total_distance = row["distance"]
        builder.add(lap)
    session = SessionMessage()
    session.timestamp = _millis(rows[-1]["t"])
    session.start_time = _millis(0)
    session.sport = sport
    session.sub_sport = sub_sport
    builder.add(session)
    return bytes(builder.build().to_bytes())


@pytest.fixture
def make_fit() -> MakeFit:
    return build_fit


@pytest.fixture
def steady_run_fit() -> bytes:
    rows = [
        {
            "t": float(i),
            "lat": 55.67 + i * 0.00003,
            "lon": 12.56,
            "distance": i * 3.0,
            "speed": 3.0,
            "altitude": 10.0,
            "hr": 140,
            "cadence": 85,
            "power": 250,
        }
        for i in range(1001)
    ]
    return build_fit(rows)

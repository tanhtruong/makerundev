import datetime as dt
import random
from xml.sax.saxutils import escape

from demo_runs import Run, Sample, laps, offset, position
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import FileType, Manufacturer, Sport, SubSport

Point = tuple[float, float] | None

FIT_SPORTS = {
    "running": (Sport.RUNNING, SubSport.GENERIC),
    "treadmill_running": (Sport.RUNNING, SubSport.TREADMILL),
    "cycling": (Sport.CYCLING, SubSport.GENERIC),
}
GPX_TYPES = {"running": "running", "treadmill_running": "running", "cycling": "cycling"}
TCX_SPORTS = {"running": "Running", "treadmill_running": "Running", "cycling": "Biking"}
NOISE_MEMORY = 0.9
SPEED_MEMORY = 0.95


def track(run: Run, rows: list[Sample], rng: random.Random) -> list[Point]:
    if run.route is None:
        return [None] * len(rows)
    north = east = 0.0
    points: list[Point] = []
    for row in rows:
        north = NOISE_MEMORY * north + rng.gauss(0, run.gps_noise_m * 0.45)
        east = NOISE_MEMORY * east + rng.gauss(0, run.gps_noise_m * 0.45)
        latitude, longitude = position(run.route, row.route_m, row.sideways_m)
        if north or east:
            latitude, longitude = offset(latitude, longitude, north, east)
        points.append((latitude, longitude))
    return points


def speeds(rows: list[Sample], rng: random.Random) -> list[float]:
    drift = 0.0
    out: list[float] = []
    for row in rows:
        drift = SPEED_MEMORY * drift + rng.gauss(0, 0.008)
        out.append(row.speed_cm_s / 100 * (1 + drift) if row.speed_cm_s else 0.0)
    return out


def fit(run: Run, rows: list[Sample], points: list[Point], speed: list[float]) -> bytes:
    def millis(seconds: float) -> int:
        return round((run.start.timestamp() + seconds) * 1000)

    sport, sub_sport = FIT_SPORTS[run.sport]
    halve = sport == Sport.RUNNING
    builder = FitFileBuilder(auto_define=True, min_string_size=50)
    file_id = FileIdMessage()
    file_id.type = FileType.ACTIVITY
    file_id.manufacturer = Manufacturer.GARMIN.value
    file_id.product = 4315
    file_id.time_created = millis(0)
    file_id.serial_number = 1
    builder.add(file_id)
    for row, point, row_speed in zip(rows, points, speed, strict=True):
        record = RecordMessage()
        record.timestamp = millis(row.t)
        record.distance = row.distance_cm / 100
        record.enhanced_speed = row_speed
        if point is not None:
            record.position_lat, record.position_long = point
        if row.altitude_cm is not None:
            record.enhanced_altitude = row.altitude_cm / 100
        if row.heart_rate is not None:
            record.heart_rate = row.heart_rate
        if row.cadence is not None:
            record.cadence = row.cadence // 2 if halve else row.cadence
        if row.power is not None:
            record.power = row.power
        if row.dynamics is not None:
            record.stance_time, record.vertical_oscillation, record.step_length = row.dynamics
        builder.add(record)
    for start, elapsed, distance in laps(run):
        lap = LapMessage()
        lap.start_time = millis(start)
        lap.timestamp = millis(start + elapsed)
        lap.total_elapsed_time = elapsed
        lap.total_distance = distance / 100
        builder.add(lap)
    session = SessionMessage()
    session.timestamp = millis(rows[-1].t)
    session.start_time = millis(0)
    session.sport = sport
    session.sub_sport = sub_sport
    builder.add(session)
    return bytes(builder.build().to_bytes())


def _time(run: Run, seconds: float) -> str:
    return (run.start + dt.timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def gpx(run: Run, rows: list[Sample], points: list[Point]) -> bytes:
    halve = run.sport != "cycling"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="makerundev demo" xmlns="http://www.topografix.com/GPX/1/1"'
        ' xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">',
        f"<trk><name>{escape(run.name)}</name><type>{GPX_TYPES[run.sport]}</type><trkseg>",
    ]
    for row, point in zip(rows, points, strict=True):
        if point is None:
            continue
        extensions = ""
        if row.heart_rate is not None:
            extensions += f"<gpxtpx:hr>{row.heart_rate}</gpxtpx:hr>"
        if row.cadence is not None:
            extensions += f"<gpxtpx:cad>{row.cadence // 2 if halve else row.cadence}</gpxtpx:cad>"
        elevation = f"<ele>{row.altitude_cm / 100:.2f}</ele>" if row.altitude_cm is not None else ""
        lines.append(
            f'<trkpt lat="{point[0]:.7f}" lon="{point[1]:.7f}">{elevation}'
            f"<time>{_time(run, row.t)}</time>"
            f"<extensions><gpxtpx:TrackPointExtension>{extensions}"
            "</gpxtpx:TrackPointExtension></extensions></trkpt>"
        )
    lines.append("</trkseg></trk></gpx>")
    return "\n".join(lines).encode()


def tcx(run: Run, rows: list[Sample], points: list[Point], speed: list[float]) -> bytes:
    halve = run.sport != "cycling"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"'
        ' xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2">',
        f'<Activities><Activity Sport="{TCX_SPORTS[run.sport]}"><Id>{_time(run, 0)}</Id>',
    ]
    bounds = laps(run) or [(0, rows[-1].t, rows[-1].distance_cm)]
    for start, elapsed, distance in bounds:
        lines.append(
            f'<Lap StartTime="{_time(run, start)}"><TotalTimeSeconds>{elapsed}</TotalTimeSeconds>'
            f"<DistanceMeters>{distance / 100:.2f}</DistanceMeters><Track>"
        )
        last = start + elapsed == rows[-1].t
        for row, point, row_speed in zip(rows, points, speed, strict=True):
            if not (start <= row.t < start + elapsed or (last and row.t == start + elapsed)):
                continue
            lines.append(_trackpoint(run, row, point, row_speed, halve))
        lines.append("</Track></Lap>")
    lines.append("</Activity></Activities></TrainingCenterDatabase>")
    return "\n".join(lines).encode()


def _trackpoint(run: Run, row: Sample, point: Point, speed: float, halve: bool) -> str:
    parts = [f"<Trackpoint><Time>{_time(run, row.t)}</Time>"]
    if point is not None:
        parts.append(
            f"<Position><LatitudeDegrees>{point[0]:.7f}</LatitudeDegrees>"
            f"<LongitudeDegrees>{point[1]:.7f}</LongitudeDegrees></Position>"
        )
    if row.altitude_cm is not None:
        parts.append(f"<AltitudeMeters>{row.altitude_cm / 100:.2f}</AltitudeMeters>")
    parts.append(f"<DistanceMeters>{row.distance_cm / 100:.2f}</DistanceMeters>")
    if row.heart_rate is not None:
        parts.append(f"<HeartRateBpm><Value>{row.heart_rate}</Value></HeartRateBpm>")
    if row.cadence is not None and not halve:
        parts.append(f"<Cadence>{row.cadence}</Cadence>")
    extension = f"<ns3:Speed>{speed:.3f}</ns3:Speed>"
    if row.cadence is not None and halve:
        extension += f"<ns3:RunCadence>{row.cadence // 2}</ns3:RunCadence>"
    if row.power is not None:
        extension += f"<ns3:Watts>{row.power}</ns3:Watts>"
    parts.append(f"<Extensions><ns3:TPX>{extension}</ns3:TPX></Extensions></Trackpoint>")
    return "".join(parts)

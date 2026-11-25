import threading

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from makerundev_server.db import ActivityRow


def effort_times(row: ActivityRow) -> list[tuple[float, float]]:
    return [(effort["distance_m"], effort["elapsed_s"]) for effort in row.best_efforts or []]


class PerformanceStore:
    def __init__(self, engine: Engine, writing: threading.Lock) -> None:
        self.engine = engine
        self.writing = writing

    def exclude(self, activity_id: int, excluded: bool) -> bool:
        with self.writing, Session(self.engine) as session:
            row = session.get(ActivityRow, activity_id)
            if row is None:
                return False
            row.excluded_from_performance = excluded
            session.commit()
            return True

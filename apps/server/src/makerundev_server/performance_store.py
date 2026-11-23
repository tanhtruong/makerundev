import logging
import threading
from collections.abc import Callable, Sequence

import polars as pl
from makerundev import Activity
from makerundev.metrics import best_efforts
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from makerundev_server.db import ActivityRow

log = logging.getLogger(__name__)


def stored_efforts(activity: Activity) -> list[dict[str, float]]:
    return [
        {"distance_m": distance, "elapsed_s": seconds}
        for distance, seconds in best_efforts(activity).items()
    ]


def effort_times(row: ActivityRow) -> list[tuple[float, float]]:
    return [(effort["distance_m"], effort["elapsed_s"]) for effort in row.best_efforts or []]


class PerformanceStore:
    def __init__(
        self, engine: Engine, writing: threading.Lock, read: Callable[[ActivityRow], Activity]
    ) -> None:
        self.engine = engine
        self.writing = writing
        self.read = read

    def fill(self, rows: Sequence[ActivityRow]) -> list[ActivityRow]:
        computed = {row.id: self._efforts(row) for row in rows if row.best_efforts is None}
        if not computed:
            return list(rows)
        with self.writing, Session(self.engine, expire_on_commit=False) as session:
            filled = {}
            for row in session.scalars(select(ActivityRow).where(ActivityRow.id.in_(computed))):
                if row.best_efforts is None:
                    row.best_efforts = computed[row.id]
                filled[row.id] = row
            session.commit()
        return [filled.get(row.id, row) for row in rows]

    def _efforts(self, row: ActivityRow) -> list[dict[str, float]]:
        try:
            return stored_efforts(self.read(row))
        except (OSError, pl.exceptions.PolarsError) as error:
            log.warning("cannot read the best efforts of activity %s: %s", row.id, error)
            return []

    def exclude(self, activity_id: int, excluded: bool) -> bool:
        with self.writing, Session(self.engine) as session:
            row = session.get(ActivityRow, activity_id)
            if row is None:
                return False
            row.excluded_from_performance = excluded
            session.commit()
            return True

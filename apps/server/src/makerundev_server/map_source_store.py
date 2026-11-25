import threading

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from makerundev_server.db import MapSourceRow
from makerundev_server.map_source import MapKind, ResolvedSource, resolve

MAP_SOURCE_ID = 1


class MapSourceStore:
    def __init__(self, engine: Engine, writing: threading.Lock) -> None:
        self.engine = engine
        self.writing = writing

    def source(self) -> ResolvedSource | None:
        with Session(self.engine) as session:
            row = session.get(MapSourceRow, MAP_SOURCE_ID)
            if row is None:
                return None
            return resolve(row.kind, row.url, row.attribution)

    def save(self, kind: MapKind, url: str | None, attribution: str | None) -> None:
        with self.writing, Session(self.engine) as session:
            row = session.get(MapSourceRow, MAP_SOURCE_ID)
            if row is None:
                row = MapSourceRow(id=MAP_SOURCE_ID)
                session.add(row)
            row.kind = kind
            row.url = url
            row.attribution = attribution
            session.commit()

    def remove(self) -> None:
        with self.writing, Session(self.engine) as session:
            row = session.get(MapSourceRow, MAP_SOURCE_ID)
            if row is not None:
                session.delete(row)
                session.commit()

from typing import Any, Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext
from makerundev_server import config
from makerundev_server.db import Base, UtcDateTime
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection


def render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]:
    if type_ == "type" and isinstance(obj, UtcDateTime):
        return "sa.DateTime()"
    return False


def run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    data_dir = config.data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{config.database_path(data_dir)}")
    with engine.connect() as connection:
        run(connection)

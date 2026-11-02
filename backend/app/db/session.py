from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

if engine.dialect.name == "sqlite":
    # The sqlite driver starts transactions lazily, so a SAVEPOINT (used for nested writes) would
    # commit the rows on release and a later rollback could not undo them. This is the SQLAlchemy
    # recipe: the driver's implicit transactions are off and BEGIN is emitted explicitly, so
    # savepoints and rollbacks behave as they do on PostgreSQL.
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_no_implicit_begin(dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine.sync_engine, "begin")
    def _sqlite_explicit_begin(conn: Connection) -> None:
        conn.exec_driver_sql("BEGIN")


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session

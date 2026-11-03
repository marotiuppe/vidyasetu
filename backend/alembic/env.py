import asyncio

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.db.base import Base

# Import every model so its table is registered on Base.metadata.
from app.modules.academics import models as _academics  # noqa: F401
from app.modules.admissions import models as _admissions  # noqa: F401
from app.modules.attendance import models as _attendance  # noqa: F401
from app.modules.audit import models as _audit  # noqa: F401
from app.modules.auth import models as _auth  # noqa: F401
from app.modules.branches import models as _branches  # noqa: F401
from app.modules.consent import models as _consent  # noqa: F401
from app.modules.datarights import models as _datarights  # noqa: F401
from app.modules.exams import models as _exams  # noqa: F401
from app.modules.fees import models as _fees  # noqa: F401
from app.modules.notices import models as _notices  # noqa: F401
from app.modules.promotion import models as _promotion  # noqa: F401
from app.modules.schools import models as _schools  # noqa: F401
from app.modules.settings import models as _settings  # noqa: F401
from app.modules.students import models as _students  # noqa: F401
from app.modules.users import models as _users  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

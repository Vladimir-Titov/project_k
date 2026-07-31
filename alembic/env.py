import asyncio

from alembic.operations import MigrationScript
from alembic.script import ScriptDirectory
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel.sql.sqltypes import AutoString

import app.modules.auth.models  # noqa: F401
import app.modules.battles.models  # noqa: F401
import app.modules.characters.models  # noqa: F401
import app.modules.content.models  # noqa: F401
import app.modules.monsters.models  # noqa: F401
from alembic import context
from app.core.config import get_db_config, get_log_config
from app.core.config.logging import setup_logging
from app.core.db.metadata import get_all_metadata, get_registered_schemas
from app.core.db.migration import add_schema_create_operations
from app.core.db.models import UTCDateTime

config = context.config

setup_logging(get_log_config())
config.set_main_option('sqlalchemy.url', get_db_config().alembic_dsn.replace('%', '%%'))

target_metadata = get_all_metadata()


def include_name(
    name: str | None,
    item_type: str,
    _parent_names: dict[str, str | None],
) -> bool:
    if item_type != 'schema':
        return True
    return name is None or name in get_registered_schemas()


def next_revision_id() -> str:
    """Return the next global, zero-padded numeric revision ID."""
    revisions = ScriptDirectory.from_config(config).walk_revisions()
    numeric_ids: list[int] = []

    for revision in revisions:
        if not revision.revision.isdecimal():
            raise ValueError(
                f'Alembic revision {revision.revision!r} is not numeric. '
                'All revisions must use sequential numeric IDs.',
            )
        numeric_ids.append(int(revision.revision))

    return f'{max(numeric_ids, default=0) + 1:04d}'


def assign_sequential_revision_id(
    _migration_context: object,
    _revision: object,
    directives: list[MigrationScript],
) -> None:
    """Apply project conventions to a newly generated migration."""
    if directives:
        directives[0].rev_id = next_revision_id()
        add_schema_create_operations(directives)


def render_item(item_type: str, item: object, _autogen_context: object) -> str | bool:
    """Render application types as stable, standalone SQLAlchemy types."""
    if item_type != 'type':
        return False
    if isinstance(item, UTCDateTime):
        return 'sa.DateTime(timezone=True)'
    if isinstance(item, AutoString):
        return 'sa.String()'
    return False


def configure_context(**kwargs: object) -> None:
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        include_schemas=True,
        include_name=include_name,
        process_revision_directives=assign_sequential_revision_id,
        render_item=render_item,
        **kwargs,
    )


def run_migrations_offline() -> None:
    configure_context(
        url=config.get_main_option('sqlalchemy.url'),
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    configure_context(connection=connection)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())

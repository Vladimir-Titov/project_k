from collections.abc import Sequence
from typing import Any

from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
from sqlalchemy.sql import Executable

type Query = str | Executable

_ASYNC_PG_DIALECT = PGDialect_asyncpg()


def compile_query(query: Query, args: Sequence[Any] = ()) -> tuple[str, tuple[Any, ...]]:
    if isinstance(query, str):
        return query, tuple(args)
    if args:
        raise ValueError('Positional arguments cannot be combined with a SQLAlchemy statement')

    compiled = query.compile(
        dialect=_ASYNC_PG_DIALECT,
        compile_kwargs={'render_postcompile': True},
    )
    position = compiled.positiontup or ()
    parameters = compiled.construct_params()
    return str(compiled), tuple(parameters[name] for name in position)

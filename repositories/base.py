from collections.abc import AsyncIterator, Iterable, Sequence
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from repositories.query import Query, compile_query


class BaseRepository:
    def __init__(
        self,
        pool: asyncpg.Pool,
        connection: asyncpg.Connection | None = None,
    ) -> None:
        self.pool = pool
        self._connection = connection

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[asyncpg.Connection]:
        if self._connection is not None:
            yield self._connection
            return

        async with self.pool.acquire() as connection:
            yield connection

    async def execute(
        self,
        query: Query,
        *args: Any,
        timeout: float | None = None,
    ) -> str:
        sql, parameters = compile_query(query, args)
        async with self.connection() as connection:
            return await connection.execute(sql, *parameters, timeout=timeout)

    async def executemany(
        self,
        query: str,
        args: Iterable[Sequence[Any]],
        *,
        timeout: float | None = None,
    ) -> None:
        async with self.connection() as connection:
            await connection.executemany(query, args, timeout=timeout)

    async def fetch(
        self,
        query: Query,
        *args: Any,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        sql, parameters = compile_query(query, args)
        async with self.connection() as connection:
            records = await connection.fetch(sql, *parameters, timeout=timeout)
        return [dict(record) for record in records]

    async def fetchrow(
        self,
        query: Query,
        *args: Any,
        timeout: float | None = None,
    ) -> dict[str, Any] | None:
        sql, parameters = compile_query(query, args)
        async with self.connection() as connection:
            record = await connection.fetchrow(sql, *parameters, timeout=timeout)
        return dict(record) if record is not None else None

    async def fetchval(
        self,
        query: Query,
        *args: Any,
        column: int = 0,
        timeout: float | None = None,
    ) -> Any:
        sql, parameters = compile_query(query, args)
        async with self.connection() as connection:
            return await connection.fetchval(
                sql,
                *parameters,
                column=column,
                timeout=timeout,
            )

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from typing import cast

import asyncpg
from fastapi import FastAPI

from repositories import Repositories
from settings import DbConfig
from web.lifespans.base import Lifespan

logger = logging.getLogger(__name__)


async def create_db_pool(config: DbConfig) -> asyncpg.Pool:
    pool_awaitable = cast(
        Awaitable[asyncpg.Pool],
        asyncpg.create_pool(
            dsn=config.asyncpg_dsn,
            min_size=config.pool_size,
            max_size=config.pool_size,
            max_queries=config.max_queries,
            max_inactive_connection_lifetime=config.max_inactive_connection_lifetime,
            timeout=config.connect_timeout,
            command_timeout=config.command_timeout,
            server_settings={'application_name': config.application_name},
        ),
    )
    pool = await pool_awaitable

    try:
        await pool.fetchval('SELECT 1')
    except Exception:
        await close_db_pool(pool, config.pool_close_timeout)
        raise

    return pool


async def close_db_pool(pool: asyncpg.Pool, timeout: float) -> None:
    try:
        await asyncio.wait_for(pool.close(), timeout=timeout)
    except TimeoutError:
        logger.exception('Timed out while closing the database pool; terminating open connections')
        pool.terminate()


def create_db_lifespan(config: DbConfig) -> Lifespan:
    @asynccontextmanager
    async def db_lifespan(application: FastAPI) -> AsyncIterator[None]:
        logger.info(
            'Creating database pool for %s:%s/%s with %s connections',
            config.host,
            config.port,
            config.database,
            config.pool_size,
        )
        pool = await create_db_pool(config)
        application.state.db_pool = pool
        application.state.repositories = Repositories(pool)
        logger.info('Database pool is ready')

        try:
            yield
        finally:
            del application.state.repositories
            await close_db_pool(pool, config.pool_close_timeout)
            del application.state.db_pool
            logger.info('Database pool is closed')

    return db_lifespan

from unittest.mock import AsyncMock, Mock

import pytest

from settings import DbConfig
from web.lifespans.db import close_db_pool, create_db_pool


@pytest.mark.asyncio
async def test_create_db_pool_creates_fixed_warm_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = Mock()
    pool.fetchval = AsyncMock(return_value=1)
    create_pool = AsyncMock(return_value=pool)
    monkeypatch.setattr('web.lifespans.db.asyncpg.create_pool', create_pool)
    config = DbConfig(
        _env_file=None,
        password='secret',
        pool_size=7,
        connect_timeout=4,
        command_timeout=12,
        max_queries=123,
        max_inactive_connection_lifetime=45,
        application_name='test-app',
    )

    result = await create_db_pool(config)

    assert result is pool
    create_pool.assert_awaited_once_with(
        dsn=config.asyncpg_dsn,
        min_size=7,
        max_size=7,
        max_queries=123,
        max_inactive_connection_lifetime=45,
        timeout=4,
        command_timeout=12,
        server_settings={'application_name': 'test-app'},
    )
    pool.fetchval.assert_awaited_once_with('SELECT 1')


@pytest.mark.asyncio
async def test_create_db_pool_closes_pool_when_health_check_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = Mock()
    pool.fetchval = AsyncMock(side_effect=RuntimeError('database error'))
    pool.close = AsyncMock()
    monkeypatch.setattr('web.lifespans.db.asyncpg.create_pool', AsyncMock(return_value=pool))

    with pytest.raises(RuntimeError, match='database error'):
        await create_db_pool(DbConfig(_env_file=None))

    pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_db_pool_closes_normally() -> None:
    pool = Mock()
    pool.close = AsyncMock()

    await close_db_pool(pool, timeout=1)

    pool.close.assert_awaited_once()
    pool.terminate.assert_not_called()


@pytest.mark.asyncio
async def test_close_db_pool_terminates_after_timeout() -> None:
    pool = Mock()
    pool.close = AsyncMock(side_effect=TimeoutError)

    await close_db_pool(pool, timeout=1)

    pool.terminate.assert_called_once()

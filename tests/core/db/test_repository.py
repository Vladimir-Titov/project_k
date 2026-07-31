import pytest
from sqlalchemy import Column, Integer, MetaData, Table, select

from app.core.db.repository import BaseRepository
from tests.core.db.fakes import FakeConnection, FakePool


@pytest.mark.asyncio
async def test_repository_acquires_connection_for_each_standalone_call() -> None:
    connection = FakeConnection()
    connection.fetch_result = [{'value': 1}]
    pool = FakePool(connection)
    repository = BaseRepository(pool)

    rows = await repository.fetch('SELECT $1::INTEGER AS value', 1)
    status = await repository.execute('UPDATE entities SET value = $1', 2)

    assert rows == [{'value': 1}]
    assert status == 'OK'
    assert pool.acquire_count == 2


@pytest.mark.asyncio
async def test_bound_repository_reuses_connection_without_pool_acquire() -> None:
    connection = FakeConnection()
    pool = FakePool(connection)
    repository = BaseRepository(pool, connection)
    table = Table('entities', MetaData(), Column('id', Integer))

    await repository.fetch(select(table).where(table.c.id == 5))

    assert pool.acquire_count == 0
    operation, sql, parameters = connection.calls[0]
    assert operation == 'fetch'
    assert 'entities.id = $1::INTEGER' in sql
    assert parameters == (5,)

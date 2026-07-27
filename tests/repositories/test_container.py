import pytest

from repositories import Repositories
from tests.repositories.fakes import FakeConnection, FakePool


def test_descriptor_returns_and_caches_typed_repository() -> None:
    repositories = Repositories(FakePool(FakeConnection()))

    first = repositories.fights
    second = repositories.fights

    assert first is second


@pytest.mark.asyncio
async def test_transaction_binds_all_repositories_to_one_connection() -> None:
    events: list[str] = []
    connection = FakeConnection(events)
    pool = FakePool(connection)
    repositories = Repositories(pool)

    async with repositories.transaction() as transaction:
        assert transaction.fights._connection is connection
        assert transaction.fights is transaction.fights

    assert pool.acquire_count == 1
    assert events == [
        'connection:enter',
        'transaction:enter',
        'transaction:exit',
        'connection:exit',
    ]


@pytest.mark.asyncio
async def test_nested_transaction_uses_same_connection_and_savepoint() -> None:
    events: list[str] = []
    connection = FakeConnection(events)
    repositories = Repositories(FakePool(connection), connection)

    async with repositories.transaction() as nested:
        assert nested.fights._connection is connection

    assert events == ['transaction:enter', 'transaction:exit']

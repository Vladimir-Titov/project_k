import pytest

from repositories import Repositories
from repositories.fights.repository import CharacterRepository, FightRepository, MobRepository
from tests.repositories.fakes import FakeConnection, FakePool


def test_properties_return_and_cache_typed_repositories() -> None:
    repositories = Repositories(FakePool(FakeConnection()))

    assert isinstance(repositories.fights, FightRepository)
    assert isinstance(repositories.characters, CharacterRepository)
    assert isinstance(repositories.mobs, MobRepository)
    assert repositories.fights is repositories.fights
    assert repositories.characters is repositories.characters
    assert repositories.mobs is repositories.mobs


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

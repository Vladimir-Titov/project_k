from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, ClassVar, Self, overload

import asyncpg

from repositories.base import BaseRepository
from repositories.fights.repository import FightRepository


class RepositoryDescriptor[RepositoryT: BaseRepository]:
    def __init__(self, repository_type: type[RepositoryT]) -> None:
        self.repository_type = repository_type

    @overload
    def __get__(self, instance: None, owner: type[Any]) -> RepositoryDescriptor[RepositoryT]: ...

    @overload
    def __get__(self, instance: RepositoryContainer, owner: type[Any]) -> RepositoryT: ...

    def __get__(
        self,
        instance: RepositoryContainer | None,
        owner: type[Any],
    ) -> RepositoryDescriptor[RepositoryT] | RepositoryT:
        del owner
        if instance is None:
            return self
        return instance.get_repository(self.repository_type)


class RepositoryContainer:
    def __init__(
        self,
        pool: asyncpg.Pool,
        connection: asyncpg.Connection | None = None,
    ) -> None:
        self.pool = pool
        self.connection = connection
        self._repositories: dict[type[BaseRepository], BaseRepository] = {}

    def get_repository[RepositoryT: BaseRepository](
        self,
        repository_type: type[RepositoryT],
    ) -> RepositoryT:
        repository = self._repositories.get(repository_type)
        if repository is None:
            repository = repository_type(self.pool, self.connection)
            self._repositories[repository_type] = repository
        return repository

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Self]:
        if self.connection is not None:
            async with self.connection.transaction():
                yield type(self)(self.pool, self.connection)
            return

        async with self.pool.acquire() as connection, connection.transaction():
            yield type(self)(self.pool, connection)


class Repositories(RepositoryContainer):
    fights: ClassVar[RepositoryDescriptor[FightRepository]] = RepositoryDescriptor(FightRepository)

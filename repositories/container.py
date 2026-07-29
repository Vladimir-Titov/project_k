from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Self

import asyncpg

from repositories.base import BaseRepository
from repositories.fights.repository import CharacterRepository, FightRepository, MobRepository


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
    @property
    def fights(self) -> FightRepository:
        return self.get_repository(FightRepository)

    @property
    def characters(self) -> CharacterRepository:
        return self.get_repository(CharacterRepository)

    @property
    def mobs(self) -> MobRepository:
        return self.get_repository(MobRepository)

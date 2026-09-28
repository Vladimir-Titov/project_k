from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Self

import asyncpg

from app.core.db.repository import BaseRepository
from app.modules.auth.repository import AccountRepository, SessionRepository
from app.modules.battles.repository import (
    FightActionRepository,
    FightActiveEffectRepository,
    FightEventRepository,
    FightParticipantRepository,
    FightParticipantStatRepository,
    FightRepository,
)
from app.modules.bots.repository import BotTemplateActionRepository, BotTemplateRepository, BotTemplateStatRepository
from app.modules.characters.repository import (
    CharacterActionRepository,
    CharacterClassRepository,
    CharacterRepository,
    CharacterStatRepository,
    ClassActionRepository,
    ClassStatRepository,
)
from app.modules.content.repository import (
    ActionDefinitionRepository,
    ActionEffectRepository,
    EffectDefinitionRepository,
    EffectRuleRepository,
)
from app.modules.locations.repository import LocationRepository, LocationTransitionRepository
from app.modules.stats.repository import StatDefinitionRepository


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
    def locations(self) -> LocationRepository:
        return self.get_repository(LocationRepository)

    @property
    def location_transitions(self) -> LocationTransitionRepository:
        return self.get_repository(LocationTransitionRepository)

    @property
    def bot_templates(self) -> BotTemplateRepository:
        return self.get_repository(BotTemplateRepository)

    @property
    def bot_template_stats(self) -> BotTemplateStatRepository:
        return self.get_repository(BotTemplateStatRepository)

    @property
    def bot_template_actions(self) -> BotTemplateActionRepository:
        return self.get_repository(BotTemplateActionRepository)

    @property
    def accounts(self) -> AccountRepository:
        return self.get_repository(AccountRepository)

    @property
    def sessions(self) -> SessionRepository:
        return self.get_repository(SessionRepository)

    @property
    def fights(self) -> FightRepository:
        return self.get_repository(FightRepository)

    @property
    def characters(self) -> CharacterRepository:
        return self.get_repository(CharacterRepository)

    @property
    def fight_participants(self) -> FightParticipantRepository:
        return self.get_repository(FightParticipantRepository)

    @property
    def fight_participant_stats(self) -> FightParticipantStatRepository:
        return self.get_repository(FightParticipantStatRepository)

    @property
    def fight_active_effects(self) -> FightActiveEffectRepository:
        return self.get_repository(FightActiveEffectRepository)

    @property
    def fight_actions(self) -> FightActionRepository:
        return self.get_repository(FightActionRepository)

    @property
    def fight_events(self) -> FightEventRepository:
        return self.get_repository(FightEventRepository)

    @property
    def character_classes(self) -> CharacterClassRepository:
        return self.get_repository(CharacterClassRepository)

    @property
    def class_stats(self) -> ClassStatRepository:
        return self.get_repository(ClassStatRepository)

    @property
    def class_actions(self) -> ClassActionRepository:
        return self.get_repository(ClassActionRepository)

    @property
    def character_stats(self) -> CharacterStatRepository:
        return self.get_repository(CharacterStatRepository)

    @property
    def character_actions(self) -> CharacterActionRepository:
        return self.get_repository(CharacterActionRepository)

    @property
    def stat_definitions(self) -> StatDefinitionRepository:
        return self.get_repository(StatDefinitionRepository)

    @property
    def action_definitions(self) -> ActionDefinitionRepository:
        return self.get_repository(ActionDefinitionRepository)

    @property
    def effect_definitions(self) -> EffectDefinitionRepository:
        return self.get_repository(EffectDefinitionRepository)

    @property
    def effect_rules(self) -> EffectRuleRepository:
        return self.get_repository(EffectRuleRepository)

    @property
    def action_effects(self) -> ActionEffectRepository:
        return self.get_repository(ActionEffectRepository)

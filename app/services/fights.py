from uuid import UUID

from app.enums.fights import FightStatus
from app.models.fights import Fight
from repositories import Repositories


class FightService:
    """Application service for fight-related use cases."""

    def __init__(self, repositories: Repositories) -> None:
        self.repositories = repositories

    async def create_fight(
        self,
        attacker_id: UUID,
        target_id: UUID,
    ) -> Fight:
        target_name = None
        character = await self.repositories.characters.get_by_id(entity_id=target_id)
        if character:
            target_name = character.nickname
        mob = await self.repositories.mobs.get_by_id(entity_id=target_id)
        if mob:
            target_name = mob.title
        if character is None and mob is None:
            raise ValueError(f'Target entity with ID {target_id} not found')
        return await self.repositories.fights.create(
            status=FightStatus.started,
            title=f'Нападение на {target_name}',
            attacker_id=attacker_id,
            target_id=target_id,
        )

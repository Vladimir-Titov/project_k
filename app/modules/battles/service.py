from uuid import UUID

from app.container import Repositories
from app.modules.battles.enums import FightSide, FightStatus
from app.modules.battles.exceptions import FightTargetNotFoundError
from app.modules.battles.models import Fight


class FightService:
    """Application service for fight-related use cases."""

    def __init__(self, repositories: Repositories) -> None:
        self.repositories = repositories

    async def create_fight(
        self,
        attacker_id: UUID,
        target_id: UUID,
    ) -> Fight:
        target_character = await self.repositories.characters.get_by_id(
            entity_id=target_id,
        )
        target_mob = await self.repositories.mobs.get_by_id(
            entity_id=target_id,
        )
        if target_character is None and target_mob is None:
            raise FightTargetNotFoundError

        target_name = target_character.nickname if target_character is not None else target_mob.title
        fight = await self.repositories.fights.create(
            status=FightStatus.started,
            title=f'Нападение на {target_name}',
        )
        target_participant = {
            'fight_id': fight.id,
            'side': FightSide.team_b,
            ('character_id' if target_character is not None else 'mob_id'): target_id,
        }
        await self.repositories.fight_participants.create_many(
            [
                {
                    'fight_id': fight.id,
                    'character_id': attacker_id,
                    'side': FightSide.team_a,
                },
                target_participant,
            ],
        )
        return fight

from uuid import UUID

from app.container import Repositories
from app.modules.battles.enums import FightSide, FightStatus
from app.modules.battles.models import Fight
from app.modules.characters.exceptions import (
    CharacterRequiredError,
    InvalidGameSessionError,
)


class FightService:
    """Application service for fight-related use cases."""

    def __init__(self, repositories: Repositories) -> None:
        self.repositories = repositories

    async def create_fight(
        self,
        *,
        account_id: UUID,
        session_id: UUID,
        target_id: UUID,
    ) -> Fight:
        async with self.repositories.transaction() as repositories:
            session = await repositories.sessions.get_active(
                session_id=session_id,
                account_id=account_id,
                for_update=True,
            )
            if session is None:
                raise InvalidGameSessionError
            if session.active_character_id is None:
                raise CharacterRequiredError

            attacker = await repositories.characters.get_active_for_account(
                character_id=session.active_character_id,
                account_id=account_id,
            )
            if attacker is None:
                raise CharacterRequiredError

            target_character = await repositories.characters.get_by_id(
                entity_id=target_id,
            )
            target_mob = await repositories.mobs.get_by_id(
                entity_id=target_id,
            )
            if target_character is None and target_mob is None:
                raise ValueError(
                    f'Target entity with ID {target_id} not found',
                )

            target_name = (
                target_character.nickname
                if target_character is not None
                else target_mob.title
            )
            fight = await repositories.fights.create(
                status=FightStatus.started,
                title=f'Нападение на {target_name}',
            )
            target_participant = {
                'fight_id': fight.id,
                'side': FightSide.team_b,
                (
                    'character_id'
                    if target_character is not None
                    else 'mob_id'
                ): target_id,
            }
            await repositories.fight_participants.create_many(
                [
                    {
                        'fight_id': fight.id,
                        'character_id': attacker.id,
                        'side': FightSide.team_a,
                    },
                    target_participant,
                ],
            )
            return fight

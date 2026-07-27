from uuid import UUID

from app.enums.fights import FightStatus
from app.models.fights import Fight
from app.services.auth import AuthService
from repositories import Repositories


class Services:
    """Application service aggregator and business-logic entry point."""

    def __init__(self, repositories: Repositories, auth: AuthService) -> None:
        self.repositories = repositories
        self.auth = auth

    async def create_fight(
        self,
        *,
        attacker_id: UUID,
        target_id: UUID,
    ) -> Fight:
        # Participants are deliberately not persisted until their repository and
        # target type are introduced. Keeping both IDs in this boundary makes that
        # extension local to the service.
        del attacker_id, target_id
        return await self.repositories.fights.create(status=FightStatus.started)

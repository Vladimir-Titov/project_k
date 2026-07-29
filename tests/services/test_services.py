from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest

from app.enums.fights import FightStatus
from app.models.fights import Fight
from app.services import FightService


@pytest.mark.asyncio
async def test_create_fight_delegates_entity_creation_to_repository() -> None:
    repositories = Mock()
    repositories.fights.create = AsyncMock(return_value=Fight(status=FightStatus.started))
    service = FightService(repositories)

    fight = await service.create_fight(
        attacker_id=uuid7(),
        target_id=uuid7(),
    )

    assert fight.status is FightStatus.started
    repositories.fights.create.assert_awaited_once_with(status=FightStatus.started)

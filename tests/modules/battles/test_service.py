from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid7

import pytest

from app.modules.battles.enums import FightSide, FightStatus
from app.modules.battles.exceptions import FightTargetNotFoundError
from app.modules.battles.models import Fight
from app.modules.battles.service import FightService
from tests.modules.auth.fakes import FakeAuthRepositories


def build_service() -> tuple[FightService, FakeAuthRepositories]:
    repositories = FakeAuthRepositories(None, uuid7())
    repositories.fights = SimpleNamespace(
        create=AsyncMock(
            return_value=Fight(
                status=FightStatus.started,
                title='Нападение на Target',
            ),
        ),
    )
    repositories.mobs = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(title='Target')),
    )
    repositories.fight_participants = SimpleNamespace(create_many=AsyncMock())
    return FightService(repositories), repositories  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_create_fight_uses_resolved_attacker_context() -> None:
    service, repositories = build_service()
    attacker_id = uuid7()
    target_id = uuid7()

    fight = await service.create_fight(
        attacker_id=attacker_id,
        target_id=target_id,
    )

    repositories.fights.create.assert_awaited_once_with(
        status=FightStatus.started,
        title='Нападение на Target',
    )
    assert repositories.fight_participants.create_many.await_args.args[0] == [
        {
            'fight_id': fight.id,
            'character_id': attacker_id,
            'side': FightSide.team_a,
        },
        {
            'fight_id': fight.id,
            'side': FightSide.team_b,
            'mob_id': target_id,
        },
    ]


@pytest.mark.asyncio
async def test_create_fight_rejects_missing_target_with_typed_error() -> None:
    service, repositories = build_service()
    repositories.mobs.get_by_id.return_value = None

    with pytest.raises(FightTargetNotFoundError):
        await service.create_fight(
            attacker_id=uuid7(),
            target_id=uuid7(),
        )

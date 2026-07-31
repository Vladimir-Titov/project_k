from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid7

import pytest

from app.modules.auth.models import Account, Session
from app.modules.battles.enums import FightSide, FightStatus
from app.modules.battles.models import Fight
from app.modules.battles.service import FightService
from app.modules.characters.exceptions import (
    CharacterRequiredError,
    InvalidGameSessionError,
)
from tests.modules.auth.fakes import FakeAuthRepositories


def build_repositories() -> tuple[FakeAuthRepositories, Account, Session]:
    account = Account(login='hero', password_hash='hash')
    character_id = uuid7()
    repositories = FakeAuthRepositories(account, character_id)
    session = Session(
        account_id=account.id,
        active_character_id=character_id,
        refresh_token_hash='hash',
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    repositories.sessions.sessions[session.id] = session
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
    repositories.fight_participants = SimpleNamespace(
        create_many=AsyncMock(),
    )
    return repositories, account, session


@pytest.mark.asyncio
async def test_create_fight_uses_character_from_server_session() -> None:
    repositories, account, session = build_repositories()
    target_id = uuid7()
    service = FightService(repositories)  # type: ignore[arg-type]

    fight = await service.create_fight(
        account_id=account.id,
        session_id=session.id,
        target_id=target_id,
    )

    assert fight.status is FightStatus.started
    repositories.fights.create.assert_awaited_once_with(
        status=FightStatus.started,
        title='Нападение на Target',
    )
    participants = repositories.fight_participants.create_many.await_args.args[0]
    assert participants == [
        {
            'fight_id': fight.id,
            'character_id': session.active_character_id,
            'side': FightSide.team_a,
        },
        {
            'fight_id': fight.id,
            'side': FightSide.team_b,
            'mob_id': target_id,
        },
    ]


@pytest.mark.asyncio
async def test_create_fight_requires_active_character() -> None:
    repositories, account, session = build_repositories()
    session.active_character_id = None
    service = FightService(repositories)  # type: ignore[arg-type]

    with pytest.raises(CharacterRequiredError):
        await service.create_fight(
            account_id=account.id,
            session_id=session.id,
            target_id=uuid7(),
        )


@pytest.mark.asyncio
async def test_create_fight_rejects_character_owned_by_other_account() -> None:
    repositories, account, session = build_repositories()
    other_account = Account(login='other', password_hash='hash')
    other_character = await repositories.characters.create_if_available(
        account_id=other_account.id,
        nickname='OtherHero',
    )
    assert other_character is not None
    session.active_character_id = other_character.id
    service = FightService(repositories)  # type: ignore[arg-type]

    with pytest.raises(CharacterRequiredError):
        await service.create_fight(
            account_id=account.id,
            session_id=session.id,
            target_id=uuid7(),
        )


@pytest.mark.asyncio
async def test_create_fight_requires_existing_server_session() -> None:
    repositories, account, session = build_repositories()
    repositories.sessions.sessions.clear()
    service = FightService(repositories)  # type: ignore[arg-type]

    with pytest.raises(InvalidGameSessionError):
        await service.create_fight(
            account_id=account.id,
            session_id=session.id,
            target_id=uuid7(),
        )


@pytest.mark.asyncio
async def test_create_fight_rejects_expired_server_session() -> None:
    repositories, account, session = build_repositories()
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    service = FightService(repositories)  # type: ignore[arg-type]

    with pytest.raises(InvalidGameSessionError):
        await service.create_fight(
            account_id=account.id,
            session_id=session.id,
            target_id=uuid7(),
        )

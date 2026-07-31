from datetime import UTC, datetime, timedelta
from uuid import uuid7

import pytest

from app.modules.auth.models import Account, Session
from app.modules.characters.exceptions import CharacterNotFoundError
from app.modules.characters.models import Character
from app.modules.game_context.exceptions import CharacterRequiredError, InvalidGameSessionError
from app.modules.game_context.service import GameContextService
from tests.modules.auth.fakes import FakeAuthRepositories


def build_context_service() -> tuple[GameContextService, FakeAuthRepositories, Account, Character, Session]:
    account = Account(login='hero', password_hash='hash')
    character = Character(account_id=account.id, nickname='Hero')
    repositories = FakeAuthRepositories(account, character.id)
    character = repositories.characters.characters[character.id]
    session = Session(
        account_id=account.id,
        active_character_id=character.id,
        refresh_token_hash='hash',
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    repositories.sessions.sessions[session.id] = session
    return GameContextService(repositories), repositories, account, character, session  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_resolve_session_and_active_character() -> None:
    service, repositories, account, character, session = build_context_service()

    context = await service.resolve_session(
        account_id=account.id,
        session_id=session.id,
        for_update=True,
    )
    active = await service.require_active_character(context)

    assert active.character_id == character.id
    assert repositories.sessions.for_update_values == [True]


@pytest.mark.asyncio
async def test_resolve_session_rejects_missing_expired_and_foreign_session() -> None:
    service, _, account, _, session = build_context_service()

    with pytest.raises(InvalidGameSessionError):
        await service.resolve_session(account_id=account.id, session_id=uuid7())
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(InvalidGameSessionError):
        await service.resolve_session(account_id=account.id, session_id=session.id)
    session.expires_at = datetime.now(UTC) + timedelta(days=1)
    with pytest.raises(InvalidGameSessionError):
        await service.resolve_session(account_id=uuid7(), session_id=session.id)


@pytest.mark.asyncio
async def test_require_active_character_rejects_empty_or_unavailable_character() -> None:
    service, repositories, account, character, session = build_context_service()
    session.active_character_id = None
    context = await service.resolve_session(account_id=account.id, session_id=session.id)
    with pytest.raises(CharacterRequiredError):
        await service.require_active_character(context)

    session.active_character_id = character.id
    character.is_archived = True
    context = await service.resolve_session(account_id=account.id, session_id=session.id)
    with pytest.raises(CharacterRequiredError):
        await service.require_active_character(context)
    repositories.characters.characters[character.id] = character


@pytest.mark.asyncio
async def test_select_character_changes_only_explicit_session() -> None:
    service, repositories, account, character, session = build_context_service()
    session.active_character_id = None
    other_session = Session(
        account_id=account.id,
        active_character_id=None,
        refresh_token_hash='other',
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    repositories.sessions.sessions[other_session.id] = other_session
    context = await service.resolve_session(account_id=account.id, session_id=session.id)

    selected = await service.select_character(context=context, character_id=character.id)

    assert selected == character
    assert session.active_character_id == character.id
    assert other_session.active_character_id is None


@pytest.mark.asyncio
async def test_select_character_rejects_foreign_or_archived_character() -> None:
    service, repositories, account, _character, session = build_context_service()
    context = await service.resolve_session(account_id=account.id, session_id=session.id)
    foreign = Character(account_id=uuid7(), nickname='Foreign')
    archived = Character(account_id=account.id, nickname='Archived', is_archived=True)
    repositories.characters.characters[foreign.id] = foreign
    repositories.characters.characters[archived.id] = archived

    for unavailable in (foreign, archived):
        with pytest.raises(CharacterNotFoundError):
            await service.select_character(
                context=context,
                character_id=unavailable.id,
            )

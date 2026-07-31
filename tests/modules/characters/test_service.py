from uuid import uuid7

import pytest

from app.core.config import AuthConfig
from app.modules.auth.passwords import PasswordHasher
from app.modules.auth.service import AuthService
from app.modules.characters.exceptions import (
    CharacterAlreadyExistsError,
    CharacterNotFoundError,
    InvalidGameSessionError,
    NicknameAlreadyExistsError,
)
from app.modules.characters.models import Character
from app.modules.characters.service import CharacterService
from tests.modules.auth.fakes import FakeAuthRepositories


async def services():
    config = AuthConfig(
        _env_file=None,
        secret_key='test-secret-key-with-at-least-32-bytes',
        password_salt='test-static-password-salt',
    )
    repositories = FakeAuthRepositories(None, uuid7())
    return (
        AuthService(config, repositories, PasswordHasher(config)),
        CharacterService(repositories),
        repositories,
    )


@pytest.mark.asyncio
async def test_create_character_selects_it_for_current_session() -> None:
    auth_service, character_service, repositories = await services()
    tokens = await auth_service.register(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    token_payload = auth_service.authenticate_access_token(
        tokens.access_token,
    )

    selection = await character_service.create(
        account_id=token_payload.account_id,
        session_id=token_payload.session_id,
        nickname='Hero',
    )
    listed = await character_service.list_for_session(
        account_id=token_payload.account_id,
        session_id=token_payload.session_id,
    )

    assert selection.character.nickname == 'Hero'
    assert selection.is_active
    assert listed == [selection]
    assert repositories.sessions.sessions[
        token_payload.session_id
    ].active_character_id == selection.character.id


@pytest.mark.asyncio
async def test_character_creation_does_not_change_other_session() -> None:
    auth_service, character_service, repositories = await services()
    registered_tokens = await auth_service.register(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    other_tokens = await auth_service.login(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    registered = auth_service.authenticate_access_token(
        registered_tokens.access_token,
    )
    other = auth_service.authenticate_access_token(
        other_tokens.access_token,
    )

    selection = await character_service.create(
        account_id=registered.account_id,
        session_id=registered.session_id,
        nickname='Hero',
    )

    assert repositories.sessions.sessions[
        registered.session_id
    ].active_character_id == selection.character.id
    assert repositories.sessions.sessions[
        other.session_id
    ].active_character_id is None


@pytest.mark.asyncio
async def test_character_creation_rejects_second_character() -> None:
    auth_service, character_service, _ = await services()
    tokens = await auth_service.register(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    payload = auth_service.authenticate_access_token(tokens.access_token)
    await character_service.create(
        account_id=payload.account_id,
        session_id=payload.session_id,
        nickname='Hero',
    )

    with pytest.raises(CharacterAlreadyExistsError):
        await character_service.create(
            account_id=payload.account_id,
            session_id=payload.session_id,
            nickname='AnotherHero',
        )


@pytest.mark.asyncio
async def test_character_creation_rejects_occupied_nickname() -> None:
    auth_service, character_service, _ = await services()
    first_tokens = await auth_service.register(
        'first',
        'password',
        ip_address=None,
        user_agent=None,
    )
    second_tokens = await auth_service.register(
        'second',
        'password',
        ip_address=None,
        user_agent=None,
    )
    first = auth_service.authenticate_access_token(
        first_tokens.access_token,
    )
    second = auth_service.authenticate_access_token(
        second_tokens.access_token,
    )
    await character_service.create(
        account_id=first.account_id,
        session_id=first.session_id,
        nickname='Hero',
    )

    with pytest.raises(NicknameAlreadyExistsError):
        await character_service.create(
            account_id=second.account_id,
            session_id=second.session_id,
            nickname='Hero',
        )


@pytest.mark.asyncio
async def test_character_api_rejects_missing_server_session() -> None:
    auth_service, character_service, _ = await services()
    tokens = await auth_service.register(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    payload = auth_service.authenticate_access_token(tokens.access_token)
    await auth_service.logout(payload.session_id)

    with pytest.raises(InvalidGameSessionError):
        await character_service.create(
            account_id=payload.account_id,
            session_id=payload.session_id,
            nickname='Hero',
        )


@pytest.mark.asyncio
async def test_select_character_updates_only_current_session() -> None:
    auth_service, character_service, repositories = await services()
    registered_tokens = await auth_service.register(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    registered = auth_service.authenticate_access_token(
        registered_tokens.access_token,
    )
    created = await character_service.create(
        account_id=registered.account_id,
        session_id=registered.session_id,
        nickname='Hero',
    )
    other_tokens = await auth_service.login(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    other = auth_service.authenticate_access_token(other_tokens.access_token)

    selected = await character_service.select(
        account_id=other.account_id,
        session_id=other.session_id,
        character_id=created.character.id,
    )
    repeated = await character_service.select(
        account_id=other.account_id,
        session_id=other.session_id,
        character_id=created.character.id,
    )

    assert selected == created
    assert repeated == created
    assert repositories.sessions.sessions[
        other.session_id
    ].active_character_id == created.character.id
    assert repositories.sessions.sessions[
        registered.session_id
    ].active_character_id == created.character.id


@pytest.mark.asyncio
async def test_select_character_rejects_unavailable_character() -> None:
    auth_service, character_service, _ = await services()
    tokens = await auth_service.register(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    payload = auth_service.authenticate_access_token(tokens.access_token)

    with pytest.raises(CharacterNotFoundError):
        await character_service.select(
            account_id=payload.account_id,
            session_id=payload.session_id,
            character_id=uuid7(),
        )


@pytest.mark.asyncio
async def test_select_character_rejects_foreign_and_archived_characters() -> None:
    auth_service, character_service, repositories = await services()
    tokens = await auth_service.register(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    payload = auth_service.authenticate_access_token(tokens.access_token)
    foreign = Character(account_id=uuid7(), nickname='Foreign')
    archived = Character(
        account_id=payload.account_id,
        nickname='Archived',
        is_archived=True,
    )
    repositories.characters.characters[foreign.id] = foreign
    repositories.characters.characters[archived.id] = archived

    for character in (foreign, archived):
        with pytest.raises(CharacterNotFoundError):
            await character_service.select(
                account_id=payload.account_id,
                session_id=payload.session_id,
                character_id=character.id,
            )


@pytest.mark.asyncio
async def test_select_character_rejects_missing_server_session() -> None:
    auth_service, character_service, repositories = await services()
    tokens = await auth_service.register(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    payload = auth_service.authenticate_access_token(tokens.access_token)
    character = Character(account_id=payload.account_id, nickname='Hero')
    repositories.characters.characters[character.id] = character
    await auth_service.logout(payload.session_id)

    with pytest.raises(InvalidGameSessionError):
        await character_service.select(
            account_id=payload.account_id,
            session_id=payload.session_id,
            character_id=character.id,
        )

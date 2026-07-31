from uuid import uuid7

import pytest

from app.modules.auth.models import Account
from app.modules.characters.exceptions import CharacterAlreadyExistsError, NicknameAlreadyExistsError
from app.modules.characters.models import Character
from app.modules.characters.service import CharacterService
from tests.modules.auth.fakes import FakeAuthRepositories


def build_service() -> tuple[CharacterService, FakeAuthRepositories, Account]:
    account = Account(login='hero', password_hash='hash')
    repositories = FakeAuthRepositories(account, uuid7())
    repositories.characters.characters.clear()
    return CharacterService(repositories), repositories, account  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_create_character_does_not_change_session_context() -> None:
    service, repositories, account = build_service()

    character = await service.create(account_id=account.id, nickname='Hero')

    assert character.nickname == 'Hero'
    assert repositories.sessions.sessions == {}
    assert await service.list(account_id=account.id) == [character]


@pytest.mark.asyncio
async def test_create_character_rejects_second_character() -> None:
    service, _, account = build_service()
    await service.create(account_id=account.id, nickname='Hero')

    with pytest.raises(CharacterAlreadyExistsError):
        await service.create(account_id=account.id, nickname='AnotherHero')


@pytest.mark.asyncio
async def test_create_character_rejects_occupied_nickname() -> None:
    service, repositories, account = build_service()
    repositories.characters.characters[uuid7()] = Character(
        account_id=uuid7(),
        nickname='Hero',
    )

    with pytest.raises(NicknameAlreadyExistsError):
        await service.create(account_id=account.id, nickname='Hero')

from decimal import Decimal
from uuid import uuid7

import pytest

from app.modules.auth.models import Account
from app.modules.characters.exceptions import CharacterAlreadyExistsError, NicknameAlreadyExistsError
from app.modules.characters.models import Character
from app.modules.characters.service import CharacterService
from tests.modules.auth.fakes import TEST_CLASS_ID, FakeAuthRepositories


def build_service() -> tuple[CharacterService, FakeAuthRepositories, Account]:
    account = Account(login='hero', password_hash='hash')
    repositories = FakeAuthRepositories(account, uuid7())
    repositories.characters.characters.clear()
    return CharacterService(repositories), repositories, account  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_create_character_does_not_change_session_context() -> None:
    service, repositories, account = build_service()

    character, character_class = await service.create(
        account_id=account.id,
        nickname='Hero',
        class_code='adventurer',
    )

    assert character.nickname == 'Hero'
    assert character_class.code == 'adventurer'
    assert len(await repositories.character_stats.list_for_character(character.id)) == 4
    assert repositories.sessions.sessions == {}
    assert await service.list(account_id=account.id) == [(character, character_class)]


@pytest.mark.asyncio
async def test_create_character_rejects_second_character() -> None:
    service, _, account = build_service()
    await service.create(account_id=account.id, nickname='Hero', class_code='adventurer')

    with pytest.raises(CharacterAlreadyExistsError):
        await service.create(account_id=account.id, nickname='AnotherHero', class_code='adventurer')


@pytest.mark.asyncio
async def test_create_character_rejects_occupied_nickname() -> None:
    service, repositories, account = build_service()
    repositories.characters.characters[uuid7()] = Character(
        account_id=uuid7(),
        nickname='Hero',
        class_id=TEST_CLASS_ID,
    )

    with pytest.raises(NicknameAlreadyExistsError):
        await service.create(account_id=account.id, nickname='Hero', class_code='adventurer')


@pytest.mark.asyncio
async def test_rest_restores_health_to_persistent_maximum() -> None:
    service, repositories, account = build_service()
    character, _ = await service.create(account_id=account.id, nickname='Hero', class_code='adventurer')
    stats = await repositories.character_stats.list_for_character(character.id)
    health_definition = next(
        definition for definition in repositories.stat_definitions.values.values() if definition.code == 'health'
    )
    health = next(item for item in stats if item.stat_definition_id == health_definition.id)
    await repositories.character_stats.set_value(health.id, Decimal(10))

    response = await service.rest(character_id=character.id, account_id=account.id)

    assert next(item.value for item in response if item.code == 'health') == Decimal(100)

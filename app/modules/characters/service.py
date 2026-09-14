from decimal import Decimal
from uuid import UUID

from app.container import Repositories
from app.modules.characters.exceptions import (
    CharacterAlreadyExistsError,
    CharacterBusyError,
    CharacterClassNotFoundError,
    CharacterNotFoundError,
    InvalidCharacterClassError,
    NicknameAlreadyExistsError,
)
from app.modules.characters.models import Character, CharacterClass
from app.modules.characters.schemas import CharacterClassResponse, StatValueResponse


class CharacterService:
    def __init__(self, repositories: Repositories) -> None:
        self.repositories = repositories

    async def create(
        self,
        *,
        account_id: UUID,
        nickname: str,
        class_code: str,
    ) -> tuple[Character, CharacterClass]:
        character_class = await self.repositories.character_classes.get_playable_by_code(class_code)
        if character_class is None:
            raise CharacterClassNotFoundError
        if await self.repositories.characters.get_by_account_id(account_id):
            raise CharacterAlreadyExistsError
        if await self.repositories.characters.get_by_nickname(nickname):
            raise NicknameAlreadyExistsError

        class_stats = await self.repositories.class_stats.list_for_class(character_class.id)
        class_actions = await self.repositories.class_actions.list_for_class(character_class.id)
        definitions = {
            definition.id: definition
            for definition in [
                await self.repositories.stat_definitions.get_by_id(item.stat_definition_id) for item in class_stats
            ]
            if definition is not None and not definition.is_archived
        }
        codes = {definition.code for definition in definitions.values()}
        if {'health', 'max_health'} - codes or not class_actions:
            raise InvalidCharacterClassError
        for item in class_stats:
            definition = definitions.get(item.stat_definition_id)
            if (
                definition is None
                or (definition.min_value is not None and item.value < definition.min_value)
                or (definition.max_value is not None and item.value > definition.max_value)
            ):
                raise InvalidCharacterClassError

        character = await self.repositories.characters.create_if_available(
            account_id=account_id,
            nickname=nickname,
            class_id=character_class.id,
        )
        if character is None:
            if await self.repositories.characters.get_by_account_id(account_id):
                raise CharacterAlreadyExistsError
            raise NicknameAlreadyExistsError

        await self.repositories.character_stats.create_many(
            [
                {
                    'character_id': character.id,
                    'stat_definition_id': item.stat_definition_id,
                    'value': item.value,
                }
                for item in class_stats
            ],
        )
        await self.repositories.character_actions.create_many(
            [
                {
                    'character_id': character.id,
                    'action_definition_id': item.action_definition_id,
                }
                for item in class_actions
            ],
        )
        return character, character_class

    async def list(self, *, account_id: UUID) -> list[tuple[Character, CharacterClass]]:
        result: list[tuple[Character, CharacterClass]] = []
        for character in await self.repositories.characters.list_active_for_account(account_id):
            character_class = await self.repositories.character_classes.get_by_id(character.class_id)
            if character_class is not None:
                result.append((character, character_class))
        return result

    async def list_classes(self) -> list[CharacterClassResponse]:
        result: list[CharacterClassResponse] = []
        for character_class in await self.repositories.character_classes.list_playable():
            stats: list[StatValueResponse] = []
            for value in await self.repositories.class_stats.list_for_class(character_class.id):
                definition = await self.repositories.stat_definitions.get_by_id(value.stat_definition_id)
                if definition is not None and not definition.is_archived:
                    stats.append(
                        StatValueResponse(
                            id=definition.id,
                            code=definition.code,
                            title=definition.title,
                            kind=definition.kind,
                            value=value.value,
                        ),
                    )
            result.append(
                CharacterClassResponse(
                    id=character_class.id,
                    code=character_class.code,
                    title=character_class.title,
                    description=character_class.description,
                    stats=stats,
                ),
            )
        return result

    async def list_stats(self, *, character_id: UUID, account_id: UUID) -> list[StatValueResponse]:
        character = await self.repositories.characters.get_active_for_account(
            character_id=character_id,
            account_id=account_id,
        )
        if character is None:
            raise CharacterNotFoundError
        result: list[StatValueResponse] = []
        for value in await self.repositories.character_stats.list_for_character(character.id):
            definition = await self.repositories.stat_definitions.get_by_id(value.stat_definition_id)
            if definition is not None and not definition.is_archived:
                result.append(
                    StatValueResponse(
                        id=definition.id,
                        code=definition.code,
                        title=definition.title,
                        kind=definition.kind,
                        value=value.value,
                    ),
                )
        return result

    async def rest(self, *, character_id: UUID, account_id: UUID) -> list[StatValueResponse]:
        character = await self.repositories.characters.get_active_for_account(
            character_id=character_id,
            account_id=account_id,
        )
        if character is None:
            raise CharacterNotFoundError
        if await self.repositories.fight_participants.get_active_for_source('character', character.id):
            raise CharacterBusyError

        values = await self.repositories.character_stats.list_for_character(character.id, for_update=True)
        by_code: dict[str, tuple[object, object]] = {}
        for value in values:
            definition = await self.repositories.stat_definitions.get_by_id(value.stat_definition_id)
            if definition is not None:
                by_code[definition.code] = (value, definition)
        health_pair = by_code.get('health')
        max_health_pair = by_code.get('max_health')
        if health_pair is None or max_health_pair is None:
            raise InvalidCharacterClassError
        health, _ = health_pair
        max_health, _ = max_health_pair
        await self.repositories.character_stats.set_value(health.id, Decimal(max_health.value))
        return await self.list_stats(character_id=character.id, account_id=account_id)

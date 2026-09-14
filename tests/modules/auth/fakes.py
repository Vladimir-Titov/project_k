import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from app.modules.auth.models import Account, Session
from app.modules.characters.models import (
    Character,
    CharacterAction,
    CharacterClass,
    CharacterStat,
    ClassAction,
    ClassStat,
)
from app.modules.stats.enums import StatKind
from app.modules.stats.models import StatDefinition

TEST_CLASS_ID = UUID(int=201)


class FakeEntityRepository:
    def __init__(self, entity_type: type, values: list[object] | None = None) -> None:
        self.entity_type = entity_type
        self.values = {value.id: value for value in values or []}

    async def get_by_id(self, entity_id: UUID):
        return self.values.get(entity_id)

    async def create_many(self, rows: list[dict[str, object]]) -> list[object]:
        result = [self.entity_type(**row) for row in rows]
        self.values.update({item.id: item for item in result})
        return result


class FakeCharacterClassRepository(FakeEntityRepository):
    async def get_playable_by_code(self, code: str) -> CharacterClass | None:
        return next(
            (item for item in self.values.values() if item.code == code and item.is_playable and not item.is_archived),
            None,
        )

    async def list_playable(self) -> list[CharacterClass]:
        return [item for item in self.values.values() if item.is_playable and not item.is_archived]


class FakeClassContentRepository(FakeEntityRepository):
    async def list_for_class(self, class_id: UUID) -> list[object]:
        return [item for item in self.values.values() if item.class_id == class_id and not item.is_archived]


class FakeCharacterContentRepository(FakeEntityRepository):
    async def list_for_character(self, character_id: UUID, *, for_update: bool = False) -> list[object]:
        del for_update
        return [item for item in self.values.values() if item.character_id == character_id and not item.is_archived]

    async def set_value(self, stat_id: UUID, value: object) -> None:
        self.values[stat_id].value = value


class FakeFightParticipantRepository:
    async def get_active_for_source(self, _source_type: str, _source_id: UUID):
        return None


class FakeAccountRepository:
    def __init__(self, account: Account | None) -> None:
        self.accounts: dict[str, Account] = {}
        if account is not None:
            self.accounts[account.login] = account

    async def get_by_login(self, login: str) -> Account | None:
        return self.accounts.get(login)

    async def get_active_by_login(self, login: str) -> Account | None:
        account = self.accounts.get(login)
        if account is None or account.is_archived:
            return None
        return account

    async def create_if_login_available(
        self,
        *,
        login: str,
        password_hash: str,
    ) -> Account | None:
        if login in self.accounts:
            return None
        account = Account(login=login, password_hash=password_hash)
        self.accounts[login] = account
        return account


class FakeCharacterRepository:
    def __init__(self, character: Character | None) -> None:
        self.characters: dict[UUID, Character] = {}
        if character is not None:
            self.characters[character.id] = character

    async def create_if_available(
        self,
        *,
        account_id: UUID,
        nickname: str,
        class_id: UUID,
    ) -> Character | None:
        if await self.get_by_account_id(account_id):
            return None
        if await self.get_by_nickname(nickname):
            return None
        character = Character(account_id=account_id, nickname=nickname, class_id=class_id)
        self.characters[character.id] = character
        return character

    async def get_by_id(self, entity_id: UUID) -> Character | None:
        return self.characters.get(entity_id)

    async def get_by_account_id(
        self,
        account_id: UUID,
    ) -> Character | None:
        return next(
            (character for character in self.characters.values() if character.account_id == account_id),
            None,
        )

    async def get_active_by_account_id(
        self,
        account_id: UUID,
    ) -> Character | None:
        character = await self.get_by_account_id(account_id)
        if character is None or character.is_archived:
            return None
        return character

    async def get_by_nickname(
        self,
        nickname: str,
    ) -> Character | None:
        return next(
            (character for character in self.characters.values() if character.nickname == nickname),
            None,
        )

    async def get_active_by_nickname(
        self,
        nickname: str,
    ) -> Character | None:
        character = await self.get_by_nickname(nickname)
        if character is None or character.is_archived:
            return None
        return character

    async def get_active_for_account(
        self,
        *,
        character_id: UUID,
        account_id: UUID,
    ) -> Character | None:
        character = self.characters.get(character_id)
        if character is None or character.account_id != account_id or character.is_archived:
            return None
        return character

    async def list_active_for_account(
        self,
        account_id: UUID,
    ) -> list[Character]:
        return [
            character
            for character in self.characters.values()
            if character.account_id == account_id and not character.is_archived
        ]


class FakeSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, Session] = {}
        self.for_update_values: list[bool] = []

    async def create_session(self, session: Session) -> Session:
        self.sessions[session.id] = session
        return session

    async def get_active(
        self,
        *,
        session_id: UUID,
        account_id: UUID,
        for_update: bool = False,
    ) -> Session | None:
        self.for_update_values.append(for_update)
        session = self.sessions.get(session_id)
        if (
            session is None
            or session.account_id != account_id
            or session.is_archived
            or session.expires_at <= datetime.now(UTC)
        ):
            return None
        return session

    async def get_for_refresh_for_update(
        self,
        session_id: UUID,
    ) -> Session | None:
        return self.sessions.get(session_id)

    async def set_active_character(
        self,
        session_id: UUID,
        character_id: UUID,
    ) -> None:
        self.sessions[session_id].active_character_id = character_id

    async def replace_refresh_token_hash(
        self,
        session_id: UUID,
        refresh_token_hash: str,
    ) -> None:
        self.sessions[session_id].refresh_token_hash = refresh_token_hash

    async def delete_by_id(self, session_id: UUID) -> None:
        self.sessions.pop(session_id, None)


class FakeAuthRepositories:
    def __init__(
        self,
        account: Account | None,
        character_id: UUID,
    ) -> None:
        character = (
            Character(
                id=character_id,
                account_id=account.id,
                nickname='ExistingHero',
                class_id=TEST_CLASS_ID,
            )
            if account is not None
            else None
        )
        self.accounts = FakeAccountRepository(account)
        self.characters = FakeCharacterRepository(character)
        self.sessions = FakeSessionRepository()
        character_class = CharacterClass(id=TEST_CLASS_ID, code='adventurer', title='Adventurer')
        self.character_classes = FakeCharacterClassRepository(CharacterClass, [character_class])
        stat_definitions = [
            StatDefinition(
                id=UUID(int=101), code='max_health', title='Max health', kind=StatKind.ATTRIBUTE, min_value=1
            ),
            StatDefinition(
                id=UUID(int=102),
                code='health',
                title='Health',
                kind=StatKind.RESOURCE,
                min_value=0,
                max_stat_definition_id=UUID(int=101),
            ),
            StatDefinition(id=UUID(int=103), code='attack', title='Attack', kind=StatKind.ATTRIBUTE, min_value=0),
            StatDefinition(id=UUID(int=104), code='defense', title='Defense', kind=StatKind.ATTRIBUTE, min_value=0),
        ]
        self.stat_definitions = FakeEntityRepository(StatDefinition, stat_definitions)
        self.class_stats = FakeClassContentRepository(
            ClassStat,
            [
                ClassStat(class_id=TEST_CLASS_ID, stat_definition_id=definition.id, value=Decimal(value))
                for definition, value in zip(stat_definitions, (100, 100, 12, 4), strict=True)
            ],
        )
        action_id = UUID(int=301)
        self.class_actions = FakeClassContentRepository(
            ClassAction,
            [ClassAction(class_id=TEST_CLASS_ID, action_definition_id=action_id)],
        )
        self.character_stats = FakeCharacterContentRepository(CharacterStat)
        self.character_actions = FakeCharacterContentRepository(CharacterAction)
        self.fight_participants = FakeFightParticipantRepository()
        if character is not None:
            self.character_stats.values = {
                item.id: item
                for item in [
                    CharacterStat(character_id=character.id, stat_definition_id=definition.id, value=Decimal(value))
                    for definition, value in zip(stat_definitions, (100, 100, 12, 4), strict=True)
                ]
            }
        self._transaction_lock = asyncio.Lock()
        self.transaction_entries = 0
        self.transaction_failures: list[type[Exception]] = []

    @asynccontextmanager
    async def transaction(self) -> Self:
        async with self._transaction_lock:
            self.transaction_entries += 1
            try:
                yield self
            except Exception as error:
                self.transaction_failures.append(type(error))
                raise

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.modules.auth.models import Account, Session
from app.modules.characters.models import Character


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
    ) -> Character | None:
        if await self.get_by_account_id(account_id):
            return None
        if await self.get_by_nickname(nickname):
            return None
        character = Character(account_id=account_id, nickname=nickname)
        self.characters[character.id] = character
        return character

    async def get_by_id(self, entity_id: UUID) -> Character | None:
        return self.characters.get(entity_id)

    async def get_by_account_id(
        self,
        account_id: UUID,
    ) -> Character | None:
        return next(
            (
                character
                for character in self.characters.values()
                if character.account_id == account_id
            ),
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
            (
                character
                for character in self.characters.values()
                if character.nickname == nickname
            ),
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
        if (
            character is None
            or character.account_id != account_id
            or character.is_archived
        ):
            return None
        return character

    async def list_active_for_account(
        self,
        account_id: UUID,
    ) -> list[Character]:
        return [
            character
            for character in self.characters.values()
            if character.account_id == account_id
            and not character.is_archived
        ]


class FakeSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, Session] = {}

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
        del for_update
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
            )
            if account is not None
            else None
        )
        self.accounts = FakeAccountRepository(account)
        self.characters = FakeCharacterRepository(character)
        self.sessions = FakeSessionRepository()
        self._transaction_lock = asyncio.Lock()

    @asynccontextmanager
    async def transaction(self) -> Self:
        async with self._transaction_lock:
            yield self

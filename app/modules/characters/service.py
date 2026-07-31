from dataclasses import dataclass
from uuid import UUID

from app.container import Repositories
from app.modules.characters.exceptions import (
    CharacterAlreadyExistsError,
    CharacterNotFoundError,
    InvalidGameSessionError,
    NicknameAlreadyExistsError,
)
from app.modules.characters.models import Character


@dataclass(frozen=True, slots=True)
class CharacterSelection:
    character: Character
    is_active: bool


class CharacterService:
    def __init__(self, repositories: Repositories) -> None:
        self.repositories = repositories

    async def create(
        self,
        *,
        account_id: UUID,
        session_id: UUID,
        nickname: str,
    ) -> CharacterSelection:
        async with self.repositories.transaction() as repositories:
            session = await repositories.sessions.get_active(
                session_id=session_id,
                account_id=account_id,
                for_update=True,
            )
            if session is None:
                raise InvalidGameSessionError

            if await repositories.characters.get_by_account_id(account_id):
                raise CharacterAlreadyExistsError
            if await repositories.characters.get_by_nickname(nickname):
                raise NicknameAlreadyExistsError

            character = await repositories.characters.create_if_available(
                account_id=account_id,
                nickname=nickname,
            )
            if character is None:
                if await repositories.characters.get_by_account_id(account_id):
                    raise CharacterAlreadyExistsError
                raise NicknameAlreadyExistsError

            await repositories.sessions.set_active_character(
                session.id,
                character.id,
            )
            return CharacterSelection(
                character=character,
                is_active=True,
            )

    async def list_for_session(
        self,
        *,
        account_id: UUID,
        session_id: UUID,
    ) -> list[CharacterSelection]:
        session = await self.repositories.sessions.get_active(
            session_id=session_id,
            account_id=account_id,
        )
        if session is None:
            raise InvalidGameSessionError

        characters = await self.repositories.characters.list_active_for_account(
            account_id,
        )
        return [
            CharacterSelection(
                character=character,
                is_active=character.id == session.active_character_id,
            )
            for character in characters
        ]

    async def select(
        self,
        *,
        account_id: UUID,
        session_id: UUID,
        character_id: UUID,
    ) -> CharacterSelection:
        async with self.repositories.transaction() as repositories:
            session = await repositories.sessions.get_active(
                session_id=session_id,
                account_id=account_id,
                for_update=True,
            )
            if session is None:
                raise InvalidGameSessionError

            character = await repositories.characters.get_active_for_account(
                character_id=character_id,
                account_id=account_id,
            )
            if character is None:
                raise CharacterNotFoundError

            await repositories.sessions.set_active_character(
                session.id,
                character.id,
            )
            return CharacterSelection(character=character, is_active=True)

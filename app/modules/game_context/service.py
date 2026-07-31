from dataclasses import dataclass
from uuid import UUID

from app.container import Repositories
from app.modules.characters.exceptions import CharacterNotFoundError
from app.modules.characters.models import Character
from app.modules.game_context.exceptions import CharacterRequiredError, InvalidGameSessionError


@dataclass(frozen=True, slots=True)
class SessionContext:
    account_id: UUID
    session_id: UUID
    active_character_id: UUID | None


@dataclass(frozen=True, slots=True)
class ActiveCharacterContext:
    account_id: UUID
    session_id: UUID
    character_id: UUID


class GameContextService:
    """Resolve and explicitly change the server-owned gameplay context."""

    def __init__(self, repositories: Repositories) -> None:
        self.repositories = repositories

    async def resolve_session(
        self,
        *,
        account_id: UUID,
        session_id: UUID,
        for_update: bool = False,
    ) -> SessionContext:
        session = await self.repositories.sessions.get_active(
            session_id=session_id,
            account_id=account_id,
            for_update=for_update,
        )
        if session is None:
            raise InvalidGameSessionError
        return SessionContext(
            account_id=session.account_id,
            session_id=session.id,
            active_character_id=session.active_character_id,
        )

    async def require_active_character(
        self,
        context: SessionContext,
    ) -> ActiveCharacterContext:
        if context.active_character_id is None:
            raise CharacterRequiredError
        character = await self.repositories.characters.get_active_for_account(
            character_id=context.active_character_id,
            account_id=context.account_id,
        )
        if character is None:
            raise CharacterRequiredError
        return ActiveCharacterContext(
            account_id=context.account_id,
            session_id=context.session_id,
            character_id=character.id,
        )

    async def select_character(
        self,
        *,
        context: SessionContext,
        character_id: UUID,
    ) -> Character:
        character = await self.repositories.characters.get_active_for_account(
            character_id=character_id,
            account_id=context.account_id,
        )
        if character is None:
            raise CharacterNotFoundError
        await self.repositories.sessions.set_active_character(
            context.session_id,
            character.id,
        )
        return character

from uuid import UUID

from app.container import Repositories
from app.modules.characters.exceptions import (
    CharacterAlreadyExistsError,
    NicknameAlreadyExistsError,
)
from app.modules.characters.models import Character


class CharacterService:
    def __init__(self, repositories: Repositories) -> None:
        self.repositories = repositories

    async def create(
        self,
        *,
        account_id: UUID,
        nickname: str,
    ) -> Character:
        if await self.repositories.characters.get_by_account_id(account_id):
            raise CharacterAlreadyExistsError
        if await self.repositories.characters.get_by_nickname(nickname):
            raise NicknameAlreadyExistsError

        character = await self.repositories.characters.create_if_available(
            account_id=account_id,
            nickname=nickname,
        )
        if character is not None:
            return character
        if await self.repositories.characters.get_by_account_id(account_id):
            raise CharacterAlreadyExistsError
        raise NicknameAlreadyExistsError

    async def list(self, *, account_id: UUID) -> list[Character]:
        return await self.repositories.characters.list_active_for_account(account_id)

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.characters.enums import CharacterClass
from app.modules.characters.service import CharacterSelection


class CreateCharacterRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)


class CharacterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nickname: str
    character_class: CharacterClass
    is_active: bool

    @classmethod
    def from_selection(
        cls,
        selection: CharacterSelection,
    ) -> CharacterResponse:
        return cls(
            id=selection.character.id,
            nickname=selection.character.nickname,
            character_class=selection.character.character_class,
            is_active=selection.is_active,
        )

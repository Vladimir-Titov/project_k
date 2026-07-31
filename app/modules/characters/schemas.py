from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.characters.enums import CharacterClass
from app.modules.characters.models import Character


class CreateCharacterRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)


class CharacterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nickname: str
    character_class: CharacterClass
    is_active: bool

    @classmethod
    def from_character(
        cls,
        character: Character,
        *,
        is_active: bool,
    ) -> CharacterResponse:
        return cls(
            id=character.id,
            nickname=character.nickname,
            character_class=character.character_class,
            is_active=is_active,
        )

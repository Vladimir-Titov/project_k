from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.characters.models import Character
from app.modules.stats.enums import StatKind


class CreateCharacterRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)
    class_code: str = Field(min_length=1, max_length=64)


class StatValueResponse(BaseModel):
    id: UUID
    code: str
    title: str
    kind: StatKind
    value: Decimal


class CharacterClassResponse(BaseModel):
    id: UUID
    code: str
    title: str
    description: str | None
    stats: list[StatValueResponse]


class CharacterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nickname: str
    class_id: UUID
    class_code: str
    is_active: bool

    @classmethod
    def from_character(
        cls,
        character: Character,
        *,
        class_code: str,
        is_active: bool,
    ) -> CharacterResponse:
        return cls(
            id=character.id,
            nickname=character.nickname,
            class_id=character.class_id,
            class_code=class_code,
            is_active=is_active,
        )

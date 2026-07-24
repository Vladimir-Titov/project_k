from sqlalchemy import Enum, Column
from sqlmodel import Field

from app.enums import CharacterClass
from app.models.base import TableBase


class Character(TableBase, table=True):
    __tablename__ = 'characters'

    account_id: str = Field(index=True, nullable=False)
    nickname: str = Field(index=True, unique=True, nullable=False)
    character_class: CharacterClass = Field(
        default=CharacterClass.ADVENTURER,
        sa_column=Column(
            Enum(
                CharacterClass,
                name="character_class",
                native_enum=False,
                validate_strings=True,
                values_callable=lambda enum: [item.value for item in enum],
            ),
            nullable=False,
        ),
    )

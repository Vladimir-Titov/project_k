from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Column, Enum
from sqlmodel import Field, Relationship

from app.core.db.models import TableBase
from app.modules.characters.enums import CharacterClass

if TYPE_CHECKING:
    from app.modules.auth.models import Account
    from app.modules.battles.models import FightParticipants


class Character(TableBase, table=True):
    __tablename__ = 'characters'

    account_id: UUID = Field(
        index=True,
        unique=True,
        nullable=False,
        foreign_key='auth.users.id',
    )
    nickname: str = Field(
        index=True,
        unique=True,
        nullable=False,
        max_length=64,
    )
    character_class: CharacterClass = Field(
        default=CharacterClass.ADVENTURER,
        sa_column=Column(
            Enum(
                CharacterClass,
                name='character_class',
                native_enum=False,
                validate_strings=True,
                values_callable=lambda enum: [item.value for item in enum],
            ),
            nullable=False,
        ),
    )
    account: Account = Relationship(back_populates='character')
    fight_participations: list[FightParticipants] = Relationship(
        back_populates='character',
    )

    def __admin_repr__(self, _request: Any) -> str:
        return self.nickname

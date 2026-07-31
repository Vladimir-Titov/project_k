from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Column, Enum, UniqueConstraint
from sqlmodel import Field, Relationship

from app.core.db.models import TableBase
from app.modules.content.enums import ActionsType

if TYPE_CHECKING:
    from app.modules.battles.models import FightActions


class Actions(TableBase, table=True):
    title: str = Field(nullable=False)
    description: str = Field(nullable=True)
    is_active: bool = Field(
        default=True,
        nullable=False,
    )
    type: ActionsType = Field(
        sa_column=Column(
            Enum(
                ActionsType,
                name='actions_type',
                native_enum=False,
                validate_strings=True,
                values_callable=lambda enum: [item.value for item in enum],
            ),
            nullable=False,
        ),
    )
    characteristic_links: list[CharacteristicsActions] = Relationship(
        back_populates='action',
    )
    fight_actions: list[FightActions] = Relationship(back_populates='action')

    def __admin_repr__(self, _request: Any) -> str:
        return self.title


class Characteristics(TableBase, table=True):
    title: str = Field(nullable=False)
    value: int = Field(nullable=False)
    description: str = Field(nullable=True)
    action_links: list[CharacteristicsActions] = Relationship(
        back_populates='characteristic',
    )

    def __admin_repr__(self, _request: Any) -> str:
        return self.title


class CharacteristicsActions(TableBase, table=True):
    __tablename__ = 'characteristics_actions'
    __table_args__ = (
        UniqueConstraint(
            'characteristic_id',
            'action_id',
            name='uq_characteristics_actions_pair',
        ),
    )

    characteristic_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='frontiers.characteristics.id',
    )
    action_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='frontiers.actions.id',
    )
    affect: int = Field(nullable=False)
    characteristic: Characteristics = Relationship(back_populates='action_links')
    action: Actions = Relationship(back_populates='characteristic_links')

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.characteristic_id} → {self.action_id}'

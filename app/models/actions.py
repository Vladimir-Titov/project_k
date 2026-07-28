from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, Enum
from sqlmodel import Field, Relationship

from app.enums.actions import ActionsType
from app.models.base import TableBase

if TYPE_CHECKING:
    from app.models.characteristics_actions import CharacteristicsActions
    from app.models.fights import FightActions


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

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship

from app.models.base import TableBase

if TYPE_CHECKING:
    from app.models.actions import Actions
    from app.models.characteristics import Characteristics


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

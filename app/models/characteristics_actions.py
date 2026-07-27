from uuid import UUID

from sqlmodel import Field


class CharacteristicsActions:
    __tablename__ = 'characteristics_actions'

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

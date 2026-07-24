from uuid import UUID

from sqlalchemy import Column, Enum
from sqlmodel import Field

from app.enums.actions import ActionsType
from app.enums.fights import FightStatus
from app.models.base import TableBase


class Fight(TableBase, table=True):
    __tablename__ = 'fights'

    status: FightStatus = Field(
        default=FightStatus.started,
        sa_column=Column(
            Enum(
                FightStatus,
                name='fight_status',
                native_enum=False,
                validate_strings=True,
                values_callable=lambda enum: [item.value for item in enum],
            ),
            nullable=False,
        ),
    )
    version: int = Field(default=1, nullable=False)
    winner_side = Field(nullable=True)  # todo: enum, может и не надо


class FightActions(TableBase, table=True):
    fight_id: UUID = Field(index=True, nullable=False, foreign_key='fights.id')
    action_id: UUID = Field(nullable=False, foreign_key='actions.id')

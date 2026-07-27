from uuid import UUID

from sqlalchemy import Column, Enum
from sqlmodel import Field

from app.enums.fights import FightSide, FightStatus
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
    winner_side: FightSide | None = Field(
        default=None,
        sa_column=Column(
            Enum(
                FightSide,
                name='fight_side',
                native_enum=False,
                validate_strings=True,
                values_callable=lambda enum: [item.value for item in enum],
            ),
            nullable=True,
        ),
    )


class FightParticipants(TableBase, table=True):
    __tablename__ = 'fight_participants'

    fight_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.fights.id')
    character_id: UUID | None = Field(nullable=True, foreign_key='frontiers.characters.id')
    mob_id: UUID | None = Field(nullable=True, foreign_key='frontiers.mobs.id')
    side: FightSide = Field(
        sa_column=Column(
            Enum(
                FightSide,
                name='fight_side',
                native_enum=False,
                validate_strings=True,
                values_callable=lambda enum: [item.value for item in enum],
            ),
            nullable=False,
        ),
    )


class FightActions(TableBase, table=True):
    __tablename__ = 'fight_actions'

    fight_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.fights.id')
    action_id: UUID = Field(nullable=False, foreign_key='frontiers.actions.id')
    initiator_participant_id: UUID = Field(
        nullable=False,
        foreign_key='frontiers.fight_participants.id',
    )
    target_participant_id: UUID = Field(
        nullable=True,
        foreign_key='frontiers.fight_participants.id',
    )

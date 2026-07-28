from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, Enum
from sqlmodel import Field, Relationship

from app.enums.fights import FightSide, FightStatus
from app.models.base import TableBase

if TYPE_CHECKING:
    from app.models.actions import Actions
    from app.models.characters import Character
    from app.models.mobs import Mob


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
    participants: list[FightParticipants] = Relationship(back_populates='fight')
    actions: list[FightActions] = Relationship(back_populates='fight')

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.id} ({self.status})'


class FightParticipants(TableBase, table=True):
    __tablename__ = 'fight_participants'
    __table_args__ = (
        CheckConstraint(
            '(character_id IS NOT NULL) <> (mob_id IS NOT NULL)',
            name='ck_fight_participant_exactly_one_actor',
        ),
    )

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
    fight: Fight = Relationship(back_populates='participants')
    character: Character = Relationship(back_populates='fight_participations')
    mob: Mob = Relationship(back_populates='fight_participations')
    initiated_actions: list[FightActions] = Relationship(
        back_populates='initiator_participant',
        sa_relationship_kwargs={
            'foreign_keys': 'FightActions.initiator_participant_id',
        },
    )
    targeted_actions: list[FightActions] = Relationship(
        back_populates='target_participant',
        sa_relationship_kwargs={
            'foreign_keys': 'FightActions.target_participant_id',
        },
    )

    def __admin_repr__(self, _request: Any) -> str:
        actor_id = self.character_id or self.mob_id
        return f'{actor_id} ({self.side})'


class FightActions(TableBase, table=True):
    __tablename__ = 'fight_actions'

    fight_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.fights.id')
    action_id: UUID = Field(nullable=False, foreign_key='frontiers.actions.id')
    initiator_participant_id: UUID = Field(
        nullable=False,
        foreign_key='frontiers.fight_participants.id',
    )
    target_participant_id: UUID | None = Field(
        default=None,
        nullable=True,
        foreign_key='frontiers.fight_participants.id',
    )
    fight: Fight = Relationship(back_populates='actions')
    action: Actions = Relationship(back_populates='fight_actions')
    initiator_participant: FightParticipants = Relationship(
        back_populates='initiated_actions',
        sa_relationship_kwargs={
            'foreign_keys': 'FightActions.initiator_participant_id',
        },
    )
    target_participant: FightParticipants = Relationship(
        back_populates='targeted_actions',
        sa_relationship_kwargs={
            'foreign_keys': 'FightActions.target_participant_id',
        },
    )

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.action_id} in {self.fight_id}'

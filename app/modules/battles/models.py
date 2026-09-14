from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, BigInteger, Column, Enum, Index, Numeric, UniqueConstraint, text
from sqlmodel import Field

from app.core.db.models import TableBase, UTCDateTime
from app.modules.battles.enums import FightSide, FightStatus
from app.modules.stats.enums import StatKind


def enum_column(enum: type[Any], name: str) -> Column[Any]:
    return Column(
        Enum(
            enum,
            name=name,
            native_enum=False,
            validate_strings=True,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
    )


class Fight(TableBase, table=True):
    __tablename__ = 'fights'

    status: FightStatus = Field(default=FightStatus.started, sa_column=enum_column(FightStatus, 'fight_status'))
    version: int = Field(default=1, nullable=False)
    turn_number: int = Field(default=1, nullable=False)
    active_participant_id: UUID | None = Field(default=None, nullable=True)
    turn_deadline_at: datetime = Field(nullable=False, sa_type=UTCDateTime)
    winner_participant_id: UUID | None = Field(default=None, nullable=True)
    finish_reason: str | None = Field(default=None, nullable=True, max_length=64)
    rng_seed: int = Field(sa_column=Column(BigInteger, nullable=False))
    rng_counter: int = Field(default=0, nullable=False)
    next_event_sequence: int = Field(default=1, nullable=False)
    content_snapshot: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    title: str = Field(nullable=False, max_length=256)

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.title} ({self.status} {self.id})'


class FightParticipants(TableBase, table=True):
    __tablename__ = 'fight_participants'
    __table_args__ = (
        UniqueConstraint('fight_id', 'source_type', 'source_id', name='uq_fight_participant_source'),
        Index(
            'uq_active_fight_participant_source',
            'source_type',
            'source_id',
            unique=True,
            postgresql_where=text('is_active = true'),
        ),
    )

    fight_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.fights.id')
    source_type: str = Field(nullable=False, max_length=32)
    source_id: UUID = Field(index=True, nullable=False)
    display_name: str = Field(nullable=False, max_length=128)
    side: FightSide = Field(sa_column=enum_column(FightSide, 'fight_side'))
    turn_order: int = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    health_before_battle: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False))
    max_health_before_battle: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False))

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.display_name} ({self.side})'


class FightParticipantStat(TableBase, table=True):
    __tablename__ = 'fight_participant_stats'
    __table_args__ = (UniqueConstraint('participant_id', 'code', name='uq_fight_participant_stat_code'),)

    participant_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.fight_participants.id')
    stat_definition_id: UUID = Field(nullable=False)
    code: str = Field(nullable=False, max_length=64)
    kind: StatKind = Field(sa_column=enum_column(StatKind, 'fight_stat_kind'))
    max_stat_code: str | None = Field(default=None, nullable=True, max_length=64)
    min_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    max_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    initial_value: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False))
    current_value: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False))


class FightActiveEffect(TableBase, table=True):
    __tablename__ = 'fight_active_effects'
    __table_args__ = (
        UniqueConstraint('target_participant_id', 'effect_code', name='uq_fight_active_effect_target_code'),
    )

    fight_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.fights.id')
    source_participant_id: UUID = Field(nullable=False, foreign_key='frontiers.fight_participants.id')
    target_participant_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.fight_participants.id')
    effect_code: str = Field(nullable=False, max_length=64)
    definition_snapshot: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    remaining_turns: int = Field(nullable=False)
    applied_turn: int = Field(nullable=False)


class FightAction(TableBase, table=True):
    __tablename__ = 'fight_actions'
    __table_args__ = (
        UniqueConstraint(
            'fight_id',
            'initiator_participant_id',
            'idempotency_key',
            name='uq_fight_action_idempotency',
        ),
    )

    fight_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.fights.id')
    initiator_participant_id: UUID = Field(nullable=False, foreign_key='frontiers.fight_participants.id')
    target_participant_id: UUID | None = Field(
        default=None,
        nullable=True,
        foreign_key='frontiers.fight_participants.id',
    )
    idempotency_key: UUID = Field(nullable=False)
    action_code: str = Field(nullable=False, max_length=64)
    turn_number: int = Field(nullable=False)
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))


class FightEvent(TableBase, table=True):
    __tablename__ = 'fight_events'
    __table_args__ = (UniqueConstraint('fight_id', 'sequence_number', name='uq_fight_event_sequence'),)

    fight_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.fights.id')
    fight_action_id: UUID | None = Field(default=None, nullable=True, foreign_key='frontiers.fight_actions.id')
    sequence_number: int = Field(nullable=False)
    event_type: str = Field(nullable=False, max_length=64)
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))

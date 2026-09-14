from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.battles.enums import FightSide, FightStatus
from app.modules.stats.enums import StatKind


class CreateFightRequest(BaseModel):
    target_id: UUID


class PerformFightActionRequest(BaseModel):
    action_code: str = Field(min_length=1, max_length=64)
    target_participant_id: UUID
    idempotency_key: UUID
    expected_version: int = Field(ge=1)


class FightTargetResponse(BaseModel):
    id: UUID
    nickname: str
    class_code: str


class FightEventResponse(BaseModel):
    sequence_number: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class FightParticipantStatResponse(BaseModel):
    code: str
    kind: StatKind
    initial_value: Decimal
    current_value: Decimal
    effective_value: Decimal


class FightActiveEffectResponse(BaseModel):
    code: str
    source_participant_id: UUID
    target_participant_id: UUID
    remaining_turns: int


class FightParticipantResponse(BaseModel):
    id: UUID
    source_type: str
    source_id: UUID
    display_name: str
    side: FightSide
    stats: list[FightParticipantStatResponse]
    effects: list[FightActiveEffectResponse]


class FightStateResponse(BaseModel):
    id: UUID
    status: FightStatus
    version: int
    turn_number: int
    active_participant_id: UUID | None
    turn_deadline_at: datetime
    winner_participant_id: UUID | None
    finish_reason: str | None
    title: str
    participants: list[FightParticipantResponse]
    available_actions: list[str]
    events: list[FightEventResponse]


class FightActionResponse(BaseModel):
    fight_action_id: UUID
    fight_id: UUID
    version: int
    turn_number: int
    status: FightStatus
    events: list[FightEventResponse]

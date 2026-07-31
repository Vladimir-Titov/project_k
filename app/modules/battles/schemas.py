from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.battles.enums import FightSide, FightStatus


class CreateFightRequest(BaseModel):
    target_id: UUID


class FightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
    is_archived: bool
    status: FightStatus
    version: int
    winner_side: FightSide | None

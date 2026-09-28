from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    title: str
    description: str | None
    image_url: str | None


class TransitionResponse(BaseModel):
    id: UUID
    destination: LocationResponse
    cooldown_seconds: int


class LocationStateResponse(BaseModel):
    location: LocationResponse
    next_movement_at: datetime | None
    server_time: datetime
    transitions: list[TransitionResponse]


class MoveRequest(BaseModel):
    transition_id: UUID

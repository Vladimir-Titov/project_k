from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.content.enums import EffectDuration, StackingPolicy, TargetPolicy


class ActionDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    title: str
    description: str | None
    image_url: str | None
    target_policy: TargetPolicy


class EffectDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    title: str
    description: str | None
    image_url: str | None
    duration: EffectDuration
    duration_turns: int | None
    stacking_policy: StackingPolicy

from pydantic import Field
from pydantic_settings import BaseSettings

from app.core.config.base import settings_config


class BattleConfig(BaseSettings):
    model_config = settings_config('BATTLE_')

    turn_duration_seconds: int = Field(default=30, ge=1)

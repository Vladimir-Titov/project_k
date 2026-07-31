from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings

from app.core.config.base import settings_config


class AppConfig(BaseSettings):
    model_config = settings_config('APP_')

    name: str = Field(default='Project K', min_length=1)
    environment: Literal['local', 'test', 'staging', 'production'] = 'local'
    debug: bool = False
    host: str = Field(default='0.0.0.0', min_length=1)
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=1, ge=1)
    docs_enabled: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: ['*'])

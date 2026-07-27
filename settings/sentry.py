from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings

from settings.base import settings_config


class SentryConfig(BaseSettings):
    """Reserved configuration for a future Sentry-compatible SDK integration."""

    model_config = settings_config('SENTRY_')

    enabled: bool = False
    dsn: SecretStr | None = None
    environment: str = Field(default='local', min_length=1)

    @field_validator('dsn', mode='before')
    @classmethod
    def empty_dsn_is_none(cls, value: object) -> object:
        return None if value == '' else value

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

from settings.base import settings_config


class AdminPanelConfig(BaseSettings):
    model_config = settings_config('ADMIN_')

    enabled: bool = False
    login: str = Field(default='admin', min_length=1)
    password: SecretStr = Field(
        default=SecretStr('local-development-admin-password'),
        min_length=8,
    )
    session_secret: SecretStr = Field(
        default=SecretStr('local-development-admin-session-secret'),
        min_length=32,
    )
    title: str = Field(default='Project K Admin', min_length=1)
    session_max_age_seconds: int = Field(default=28_800, ge=1)
    secure_cookies: bool = False

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

from app.core.config.base import settings_config


class AuthConfig(BaseSettings):
    model_config = settings_config('AUTH_')

    secret_key: SecretStr = Field(
        default=SecretStr('local-development-secret-key-change-me'),
        min_length=32,
    )
    algorithm: Literal['HS256'] = 'HS256'
    issuer: str = Field(default='project-k', min_length=1)
    audience: str = Field(default='project-k-client', min_length=1)
    password_salt: SecretStr = Field(
        default=SecretStr('local-development-password-salt'),
        min_length=8,
    )
    access_token_ttl_days: int = Field(default=3, ge=1)
    refresh_token_ttl_days: int = Field(default=30, ge=1)

from urllib.parse import quote

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

from app.core.config.base import settings_config


class DbConfig(BaseSettings):
    model_config = settings_config('DB_')

    host: str = Field(default='127.0.0.1', min_length=1)
    port: int = Field(default=40321, ge=1, le=65535)
    database: str = Field(default='postgres', min_length=1)
    user: str = Field(default='postgres', min_length=1)
    password: SecretStr = SecretStr('postgres')
    pool_size: int = Field(default=5, ge=1)
    connect_timeout: float = Field(default=10, gt=0)
    command_timeout: float = Field(default=30, gt=0)
    max_queries: int = Field(default=50_000, ge=1)
    max_inactive_connection_lifetime: float = Field(default=300, ge=0)
    pool_close_timeout: float = Field(default=10, gt=0)
    application_name: str = Field(default='project-k', min_length=1)

    def _dsn(self, scheme: str) -> str:
        user = quote(self.user, safe='')
        password = quote(self.password.get_secret_value(), safe='')
        database = quote(self.database, safe='')
        host = f'[{self.host}]' if ':' in self.host and not self.host.startswith('[') else self.host
        return f'{scheme}://{user}:{password}@{host}:{self.port}/{database}'

    @property
    def asyncpg_dsn(self) -> str:
        return self._dsn('postgresql')

    @property
    def alembic_dsn(self) -> str:
        return self._dsn('postgresql+asyncpg')

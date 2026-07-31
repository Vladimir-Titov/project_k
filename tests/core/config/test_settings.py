from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import (
    AdminPanelConfig,
    AppConfig,
    AuthConfig,
    DbConfig,
    LogConfig,
    SentryConfig,
)


def test_app_config_defaults_without_dotenv() -> None:
    config = AppConfig(_env_file=None)

    assert config.port == 8000
    assert config.workers == 1
    assert config.cors_origins == ['*']


def test_environment_has_priority_over_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dotenv_path = tmp_path / '.env'
    dotenv_path.write_text('APP_PORT=9000\n', encoding='utf-8')
    monkeypatch.setenv('APP_PORT', '9001')

    config = AppConfig(_env_file=dotenv_path)

    assert config.port == 9001


def test_cors_origins_are_loaded_from_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APP_CORS_ORIGINS', '["https://game.example", "https://admin.example"]')

    config = AppConfig(_env_file=None)

    assert config.cors_origins == ['https://game.example', 'https://admin.example']


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('port', 0),
        ('workers', 0),
    ],
)
def test_app_config_rejects_invalid_values(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        AppConfig(_env_file=None, **{field: value})


def test_db_config_builds_encoded_dsns_and_hides_password() -> None:
    config = DbConfig(
        _env_file=None,
        host='db.example',
        port=5432,
        database='project k',
        user='game user',
        password='p@ss:word',
    )

    assert config.asyncpg_dsn == 'postgresql://game%20user:p%40ss%3Aword@db.example:5432/project%20k'
    assert config.alembic_dsn == 'postgresql+asyncpg://game%20user:p%40ss%3Aword@db.example:5432/project%20k'
    assert 'p@ss:word' not in repr(config)
    assert "password=SecretStr('**********')" in repr(config)


@pytest.mark.parametrize(
    'config_type',
    [AdminPanelConfig, AppConfig, AuthConfig, DbConfig, LogConfig, SentryConfig],
)
def test_unknown_dotenv_values_are_ignored(config_type: type[object], tmp_path: Path) -> None:
    dotenv_path = tmp_path / '.env'
    dotenv_path.write_text('UNKNOWN_SETTING=value\n', encoding='utf-8')

    config_type(_env_file=dotenv_path)


def test_log_levels_are_normalized() -> None:
    config = LogConfig(_env_file=None, level='debug', sql_level='error')

    assert config.level == 'DEBUG'
    assert config.sql_level == 'ERROR'


def test_empty_sentry_dsn_is_disabled_value() -> None:
    config = SentryConfig(_env_file=None, dsn='')

    assert config.dsn is None


def test_auth_config_hides_signing_secret() -> None:
    config = AuthConfig(
        _env_file=None,
        secret_key='test-secret-key-with-at-least-32-bytes',
        password_salt='test-static-password-salt',
    )

    representation = repr(config)
    assert 'test-secret-key-with-at-least-32-bytes' not in representation
    assert 'test-static-password-salt' not in representation
    assert config.access_token_ttl_days == 3


def test_auth_config_rejects_short_signing_secret() -> None:
    with pytest.raises(ValidationError):
        AuthConfig(_env_file=None, secret_key='too-short')


def test_admin_config_hides_credentials() -> None:
    config = AdminPanelConfig(
        _env_file=None,
        password='staff-password',
        session_secret='test-admin-session-secret-at-least-32-bytes',
    )

    representation = repr(config)
    assert 'staff-password' not in representation
    assert 'test-admin-session-secret-at-least-32-bytes' not in representation

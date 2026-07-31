from functools import lru_cache

from app.core.config.admin import AdminPanelConfig
from app.core.config.app import AppConfig
from app.core.config.auth import AuthConfig
from app.core.config.db import DbConfig
from app.core.config.logging import LogConfig
from app.core.config.sentry import SentryConfig


@lru_cache
def get_admin_panel_config() -> AdminPanelConfig:
    return AdminPanelConfig()


@lru_cache
def get_app_config() -> AppConfig:
    return AppConfig()


@lru_cache
def get_auth_config() -> AuthConfig:
    return AuthConfig()


@lru_cache
def get_db_config() -> DbConfig:
    return DbConfig()


@lru_cache
def get_log_config() -> LogConfig:
    return LogConfig()


@lru_cache
def get_sentry_config() -> SentryConfig:
    return SentryConfig()


__all__ = [
    'AdminPanelConfig',
    'AppConfig',
    'AuthConfig',
    'DbConfig',
    'LogConfig',
    'SentryConfig',
    'get_admin_panel_config',
    'get_app_config',
    'get_auth_config',
    'get_db_config',
    'get_log_config',
    'get_sentry_config',
]

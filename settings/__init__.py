from functools import lru_cache

from settings.app import AppConfig
from settings.auth import AuthConfig
from settings.db import DbConfig
from settings.logging import LogConfig
from settings.sentry import SentryConfig


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
    'AppConfig',
    'AuthConfig',
    'DbConfig',
    'LogConfig',
    'SentryConfig',
    'get_app_config',
    'get_auth_config',
    'get_db_config',
    'get_log_config',
    'get_sentry_config',
]

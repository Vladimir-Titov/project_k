import logging
import logging.config
from datetime import UTC, datetime
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings

from settings.base import settings_config

LOG_LEVELS = frozenset({'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'})
LOG_FORMAT = '%(asctime)s | %(levelname)s | %(name)s:%(lineno)d | %(message)s'


class LogConfig(BaseSettings):
    model_config = settings_config('LOG_')

    level: str = 'INFO'
    sql_level: str = 'WARNING'
    access_log: bool = True

    @field_validator('level', 'sql_level', mode='before')
    @classmethod
    def validate_log_level(cls, value: object) -> str:
        level = str(value).upper()
        if level not in LOG_LEVELS:
            allowed = ', '.join(sorted(LOG_LEVELS))
            raise ValueError(f'log level must be one of: {allowed}')
        return level


class UtcFormatter(logging.Formatter):
    def formatTime(  # noqa: N802
        self,
        record: logging.LogRecord,
        datefmt: str | None = None,
    ) -> str:
        del datefmt
        timestamp = datetime.fromtimestamp(record.created, tz=UTC)
        return timestamp.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def logging_config(config: LogConfig) -> dict[str, Any]:
    access_level = config.level if config.access_log else 'WARNING'
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                '()': UtcFormatter,
                'format': LOG_FORMAT,
            },
        },
        'handlers': {
            'stdout': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'stream': 'ext://sys.stdout',
            },
        },
        'root': {
            'handlers': ['stdout'],
            'level': config.level,
        },
        'loggers': {
            'alembic': {'handlers': [], 'level': config.level, 'propagate': True},
            'sqlalchemy': {'handlers': [], 'level': config.sql_level, 'propagate': True},
            'uvicorn': {'handlers': [], 'level': config.level, 'propagate': True},
            'uvicorn.access': {'handlers': [], 'level': access_level, 'propagate': True},
            'uvicorn.error': {'handlers': [], 'level': config.level, 'propagate': True},
        },
    }


def setup_logging(config: LogConfig) -> None:
    logging.config.dictConfig(logging_config(config))

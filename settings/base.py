from pathlib import Path

from pydantic_settings import SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / '.env'


def settings_config(env_prefix: str) -> SettingsConfigDict:
    return SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding='utf-8',
        env_prefix=env_prefix,
        case_sensitive=False,
        extra='ignore',
        validate_default=True,
    )

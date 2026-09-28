from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings

from app.core.config.base import settings_config


class StorageConfig(BaseSettings):
    model_config = settings_config('S3_')

    enabled: bool = False
    endpoint_url: AnyHttpUrl = AnyHttpUrl('http://127.0.0.1:9000')
    public_url: AnyHttpUrl = AnyHttpUrl('http://127.0.0.1:9000/project-k')
    access_key: str = Field(default='rustfsadmin', min_length=1)
    secret_key: SecretStr = SecretStr('rustfsadmin')
    bucket: str = Field(default='project-k', min_length=3)
    region: str = 'us-east-1'
    initialize_local_bucket: bool = False
    max_image_size_bytes: int = Field(default=5 * 1024 * 1024, gt=0)

from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import AuthConfig, DbConfig
from app.core.files.s3 import S3FileRepository
from app.lifespans.admin import create_admin_lifespan
from app.lifespans.base import Lifespan, compose_lifespans
from app.lifespans.db import create_db_lifespan
from app.lifespans.services import create_services_lifespan
from app.lifespans.storage import create_storage_lifespan
from app.modules.auth.passwords import PasswordHasher


def create_lifespan(
    db_config: DbConfig,
    auth_config: AuthConfig,
    password_hasher: PasswordHasher,
    admin_engine: AsyncEngine | None = None,
    files: S3FileRepository | None = None,
) -> Lifespan:
    lifespans = [
        create_db_lifespan(db_config),
        create_services_lifespan(auth_config, password_hasher),
    ]
    if admin_engine is not None:
        lifespans.append(create_admin_lifespan(admin_engine))
    if files is not None:
        lifespans.append(create_storage_lifespan(files))
    return compose_lifespans(*lifespans)


__all__ = ['Lifespan', 'compose_lifespans', 'create_lifespan']

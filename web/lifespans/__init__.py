from sqlalchemy.ext.asyncio import AsyncEngine

from settings import AuthConfig, DbConfig
from web.lifespans.admin import create_admin_lifespan
from web.lifespans.base import Lifespan, compose_lifespans
from web.lifespans.db import create_db_lifespan
from web.lifespans.services import create_services_lifespan


def create_lifespan(
    db_config: DbConfig,
    auth_config: AuthConfig,
    admin_engine: AsyncEngine | None = None,
) -> Lifespan:
    lifespans = [
        create_db_lifespan(db_config),
        create_services_lifespan(auth_config),
    ]
    if admin_engine is not None:
        lifespans.append(create_admin_lifespan(admin_engine))
    return compose_lifespans(*lifespans)


__all__ = ['Lifespan', 'compose_lifespans', 'create_lifespan']

from settings import AuthConfig, DbConfig
from web.lifespans.base import Lifespan, compose_lifespans
from web.lifespans.db import create_db_lifespan
from web.lifespans.services import create_services_lifespan


def create_lifespan(db_config: DbConfig, auth_config: AuthConfig) -> Lifespan:
    return compose_lifespans(
        create_db_lifespan(db_config),
        create_services_lifespan(auth_config),
    )


__all__ = ['Lifespan', 'compose_lifespans', 'create_lifespan']

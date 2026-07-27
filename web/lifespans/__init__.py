from settings import DbConfig
from web.lifespans.base import Lifespan, compose_lifespans
from web.lifespans.db import create_db_lifespan


def create_lifespan(db_config: DbConfig) -> Lifespan:
    return compose_lifespans(
        create_db_lifespan(db_config),
    )


__all__ = ['Lifespan', 'compose_lifespans', 'create_lifespan']

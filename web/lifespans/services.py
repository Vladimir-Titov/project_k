from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.services import AuthService, FightService
from settings import AuthConfig
from web.lifespans.base import Lifespan


def create_services_lifespan(config: AuthConfig) -> Lifespan:
    @asynccontextmanager
    async def services_lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.auth_service = AuthService(config)
        application.state.fight_service = FightService(application.state.repositories)
        try:
            yield
        finally:
            del application.state.fight_service
            del application.state.auth_service

    return services_lifespan

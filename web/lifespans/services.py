from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.services import AuthService, Services
from settings import AuthConfig
from web.lifespans.base import Lifespan


def create_services_lifespan(config: AuthConfig) -> Lifespan:
    @asynccontextmanager
    async def services_lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.services = Services(
            repositories=application.state.repositories,
            auth=AuthService(config),
        )
        try:
            yield
        finally:
            del application.state.services

    return services_lifespan

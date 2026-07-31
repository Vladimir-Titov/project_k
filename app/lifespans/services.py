from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import AuthConfig
from app.lifespans.base import Lifespan
from app.modules.auth.passwords import PasswordHasher
from app.modules.auth.service import AuthService
from app.modules.battles.service import FightService
from app.modules.characters.service import CharacterService


def create_services_lifespan(
    config: AuthConfig,
    password_hasher: PasswordHasher,
) -> Lifespan:
    @asynccontextmanager
    async def services_lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.auth_service = AuthService(
            config,
            application.state.repositories,
            password_hasher,
        )
        application.state.character_service = CharacterService(
            application.state.repositories,
        )
        application.state.fight_service = FightService(application.state.repositories)
        try:
            yield
        finally:
            del application.state.fight_service
            del application.state.character_service
            del application.state.auth_service

    return services_lifespan

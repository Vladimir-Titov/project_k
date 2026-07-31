from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.container import Repositories
from app.modules.auth.exceptions import AuthenticationRequiredError
from app.modules.auth.service import AccountTokenPayload, AuthService
from app.modules.battles.service import FightService
from app.modules.characters.service import CharacterService
from app.modules.game_context.service import (
    ActiveCharacterContext,
    GameContextService,
    SessionContext,
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


async def get_unit_of_work(request: Request) -> AsyncIterator[Repositories]:
    async with request.app.state.repositories.transaction() as repositories:
        yield repositories


def get_character_service(
    repositories: Annotated[Repositories, Depends(get_unit_of_work)],
) -> CharacterService:
    return CharacterService(repositories)


def get_fight_service(
    repositories: Annotated[Repositories, Depends(get_unit_of_work)],
) -> FightService:
    return FightService(repositories)


def get_game_context_service(
    repositories: Annotated[Repositories, Depends(get_unit_of_work)],
) -> GameContextService:
    return GameContextService(repositories)


def get_current_account_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AccountTokenPayload:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise AuthenticationRequiredError
    return auth_service.authenticate_access_token(credentials.credentials)


async def get_session_context(
    token_payload: Annotated[AccountTokenPayload, Depends(get_current_account_token_payload)],
    context_service: Annotated[GameContextService, Depends(get_game_context_service)],
) -> SessionContext:
    return await context_service.resolve_session(
        account_id=token_payload.account_id,
        session_id=token_payload.session_id,
    )


async def get_locked_session_context(
    token_payload: Annotated[AccountTokenPayload, Depends(get_current_account_token_payload)],
    context_service: Annotated[GameContextService, Depends(get_game_context_service)],
) -> SessionContext:
    return await context_service.resolve_session(
        account_id=token_payload.account_id,
        session_id=token_payload.session_id,
        for_update=True,
    )


async def get_active_character_context(
    session_context: Annotated[SessionContext, Depends(get_locked_session_context)],
    context_service: Annotated[GameContextService, Depends(get_game_context_service)],
) -> ActiveCharacterContext:
    return await context_service.require_active_character(session_context)

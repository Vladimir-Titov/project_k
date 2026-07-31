from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.auth.exceptions import (
    AuthenticationRequiredError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    LoginAlreadyExistsError,
)
from app.modules.battles.exceptions import FightTargetNotFoundError
from app.modules.characters.exceptions import (
    CharacterAlreadyExistsError,
    CharacterNotFoundError,
    NicknameAlreadyExistsError,
)
from app.modules.game_context.exceptions import CharacterRequiredError, InvalidGameSessionError

type ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def _json_error_handler(status_code: int, detail: str) -> ExceptionHandler:
    async def handler(_request: Request, _error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={'detail': detail})

    return handler


def register_exception_handlers(application: FastAPI) -> None:
    mappings: tuple[tuple[type[Exception], int, str], ...] = (
        (AuthenticationRequiredError, status.HTTP_401_UNAUTHORIZED, 'Not authenticated'),
        (InvalidAccessTokenError, status.HTTP_401_UNAUTHORIZED, 'Invalid or expired access token'),
        (InvalidRefreshTokenError, status.HTTP_401_UNAUTHORIZED, 'Invalid or expired refresh token'),
        (InvalidCredentialsError, status.HTTP_401_UNAUTHORIZED, 'Incorrect login or password'),
        (LoginAlreadyExistsError, status.HTTP_409_CONFLICT, 'User with this login already exists'),
        (InvalidGameSessionError, status.HTTP_401_UNAUTHORIZED, 'invalid_or_expired_session'),
        (CharacterRequiredError, status.HTTP_409_CONFLICT, 'character_required'),
        (CharacterAlreadyExistsError, status.HTTP_409_CONFLICT, 'character_already_exists'),
        (NicknameAlreadyExistsError, status.HTTP_409_CONFLICT, 'nickname_already_exists'),
        (CharacterNotFoundError, status.HTTP_404_NOT_FOUND, 'character_not_found'),
        (FightTargetNotFoundError, status.HTTP_404_NOT_FOUND, 'fight_target_not_found'),
    )
    for error_type, status_code, detail in mappings:
        application.add_exception_handler(
            error_type,
            _json_error_handler(status_code, detail),
        )

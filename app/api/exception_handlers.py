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
from app.modules.battles.exceptions import (
    FightActionNotAvailableError,
    FightFinishedError,
    FightNotFoundError,
    FightTargetNotFoundError,
    FightUnavailableError,
    InvalidFightActionError,
    NotYourTurnError,
    StaleFightVersionError,
    TurnExpiredError,
)
from app.modules.characters.exceptions import (
    CharacterAlreadyExistsError,
    CharacterBusyError,
    CharacterClassNotFoundError,
    CharacterNotFoundError,
    InvalidCharacterClassError,
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
        (CharacterClassNotFoundError, status.HTTP_422_UNPROCESSABLE_CONTENT, 'character_class_not_found'),
        (InvalidCharacterClassError, status.HTTP_409_CONFLICT, 'invalid_character_class'),
        (CharacterBusyError, status.HTTP_409_CONFLICT, 'character_busy'),
        (FightTargetNotFoundError, status.HTTP_404_NOT_FOUND, 'fight_target_not_found'),
        (FightNotFoundError, status.HTTP_404_NOT_FOUND, 'fight_not_found'),
        (FightUnavailableError, status.HTTP_409_CONFLICT, 'fight_unavailable'),
        (FightFinishedError, status.HTTP_409_CONFLICT, 'fight_finished'),
        (NotYourTurnError, status.HTTP_409_CONFLICT, 'not_your_turn'),
        (TurnExpiredError, status.HTTP_409_CONFLICT, 'turn_expired'),
        (StaleFightVersionError, status.HTTP_409_CONFLICT, 'stale_fight_version'),
        (FightActionNotAvailableError, status.HTTP_409_CONFLICT, 'fight_action_not_available'),
        (InvalidFightActionError, status.HTTP_422_UNPROCESSABLE_CONTENT, 'invalid_fight_action'),
    )
    for error_type, status_code, detail in mappings:
        application.add_exception_handler(
            error_type,
            _json_error_handler(status_code, detail),
        )

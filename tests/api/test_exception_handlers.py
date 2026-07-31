import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.exception_handlers import register_exception_handlers
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


@pytest.mark.parametrize(
    ('error_type', 'status_code', 'detail'),
    [
        (AuthenticationRequiredError, 401, 'Not authenticated'),
        (InvalidAccessTokenError, 401, 'Invalid or expired access token'),
        (InvalidRefreshTokenError, 401, 'Invalid or expired refresh token'),
        (InvalidCredentialsError, 401, 'Incorrect login or password'),
        (LoginAlreadyExistsError, 409, 'User with this login already exists'),
        (InvalidGameSessionError, 401, 'invalid_or_expired_session'),
        (CharacterRequiredError, 409, 'character_required'),
        (CharacterAlreadyExistsError, 409, 'character_already_exists'),
        (NicknameAlreadyExistsError, 409, 'nickname_already_exists'),
        (CharacterNotFoundError, 404, 'character_not_found'),
        (FightTargetNotFoundError, 404, 'fight_target_not_found'),
    ],
)
def test_application_exception_mapping(
    error_type: type[Exception],
    status_code: int,
    detail: str,
) -> None:
    application = FastAPI()
    register_exception_handlers(application)

    @application.get('/failure')
    async def failure() -> None:
        raise error_type

    response = TestClient(application, raise_server_exceptions=False).get('/failure')

    assert response.status_code == status_code
    assert response.json() == {'detail': detail}

from uuid import UUID

import jwt
import pytest

from app.services import AuthService, InvalidTokenError
from settings import AuthConfig


def auth_service() -> AuthService:
    return AuthService(
        AuthConfig(
            _env_file=None,
            secret_key='test-secret-key-with-at-least-32-bytes',
            issuer='test-project',
            audience='test-client',
        ),
    )


def test_login_issues_signed_access_and_refresh_tokens() -> None:
    service = auth_service()

    tokens = service.login('hero', 'password')
    access_payload = service.authenticate_access_token(tokens.access_token)
    refreshed_tokens = service.refresh(tokens.refresh_token)

    assert isinstance(access_payload.character_id, UUID)
    assert service.authenticate_access_token(refreshed_tokens.access_token).character_id == access_payload.character_id
    assert tokens.expires_in == 15 * 60
    assert jwt.decode(tokens.access_token, options={'verify_signature': False})['token_type'] == 'access'
    assert jwt.decode(tokens.refresh_token, options={'verify_signature': False})['token_type'] == 'refresh'


def test_token_types_cannot_be_interchanged() -> None:
    service = auth_service()
    tokens = service.login('hero', 'password')

    with pytest.raises(InvalidTokenError):
        service.authenticate_access_token(tokens.refresh_token)

    with pytest.raises(InvalidTokenError):
        service.refresh(tokens.access_token)


def test_invalid_signature_is_rejected() -> None:
    tokens = auth_service().login('hero', 'password')
    other_service = AuthService(
        AuthConfig(
            _env_file=None,
            secret_key='another-test-secret-with-at-least-32-bytes',
        ),
    )

    with pytest.raises(InvalidTokenError):
        other_service.authenticate_access_token(tokens.access_token)

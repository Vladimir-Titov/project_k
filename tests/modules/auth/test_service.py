import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

import jwt
import pytest

from app.core.config import AuthConfig
from app.modules.auth.exceptions import InvalidCredentialsError, InvalidTokenError, LoginAlreadyExistsError
from app.modules.auth.models import Account
from app.modules.auth.passwords import PasswordHasher
from app.modules.auth.service import AuthService
from tests.modules.auth.fakes import FakeAuthRepositories


def auth_config(**overrides: object) -> AuthConfig:
    values = {
        'secret_key': 'test-secret-key-with-at-least-32-bytes',
        'password_salt': 'test-static-password-salt',
        'issuer': 'test-project',
        'audience': 'test-client',
        **overrides,
    }
    return AuthConfig(
        _env_file=None,
        **values,
    )


async def auth_service(
    **config_overrides: object,
) -> tuple[AuthService, FakeAuthRepositories]:
    config = auth_config(**config_overrides)
    password_hasher = PasswordHasher(config)
    account = Account(
        login='hero',
        password_hash=await password_hasher.hash('password'),
    )
    repositories = FakeAuthRepositories(account, uuid7())
    return (
        AuthService(config, repositories, password_hasher),
        repositories,
    )


async def empty_auth_service() -> tuple[AuthService, FakeAuthRepositories]:
    config = auth_config()
    password_hasher = PasswordHasher(config)
    repositories = FakeAuthRepositories(None, uuid7())
    return (
        AuthService(config, repositories, password_hasher),
        repositories,
    )


@pytest.mark.asyncio
async def test_password_hash_uses_argon2id_and_static_salt() -> None:
    hasher = PasswordHasher(auth_config())

    first_hash = await hasher.hash('password')
    second_hash = await hasher.hash('password')

    assert first_hash.startswith('$argon2id$')
    assert first_hash == second_hash
    assert 'password' not in first_hash
    assert await hasher.verify('password', first_hash)
    assert not await hasher.verify('wrong', first_hash)
    assert not await hasher.verify('password', 'not-an-argon2-hash')


@pytest.mark.asyncio
async def test_register_creates_account_session_and_account_only_tokens() -> None:
    service, repositories = await empty_auth_service()

    tokens = await service.register(
        'new-hero',
        'password',
        ip_address='127.0.0.1',
        user_agent='test-agent',
    )
    payload = service.authenticate_access_token(tokens.access_token)
    account = repositories.accounts.accounts['new-hero']
    session = repositories.sessions.sessions[payload.session_id]
    access_claims = jwt.decode(
        tokens.access_token,
        options={'verify_signature': False},
    )
    refresh_claims = jwt.decode(
        tokens.refresh_token,
        options={'verify_signature': False},
    )

    assert payload.account_id == account.id
    assert repositories.characters.characters == {}
    assert 'character_id' not in access_claims
    assert 'character_id' not in refresh_claims
    assert account.password_hash != 'password'
    assert await service.password_hasher.verify(
        'password',
        account.password_hash,
    )
    assert session.account_id == account.id
    assert session.active_character_id is None
    assert session.ip_address == '127.0.0.1'
    assert session.user_agent == 'test-agent'


@pytest.mark.asyncio
async def test_register_rejects_existing_login() -> None:
    service, repositories = await empty_auth_service()
    await service.register(
        'new-hero',
        'password',
        ip_address=None,
        user_agent=None,
    )

    with pytest.raises(LoginAlreadyExistsError):
        await service.register(
            'new-hero',
            'another-password',
            ip_address=None,
            user_agent=None,
        )

    assert len(repositories.accounts.accounts) == 1
    assert len(repositories.sessions.sessions) == 1


@pytest.mark.asyncio
async def test_concurrent_registration_allows_only_one_login() -> None:
    service, repositories = await empty_auth_service()

    results = await asyncio.gather(
        service.register(
            'new-hero',
            'first-password',
            ip_address=None,
            user_agent=None,
        ),
        service.register(
            'new-hero',
            'second-password',
            ip_address=None,
            user_agent=None,
        ),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(
        isinstance(result, LoginAlreadyExistsError)
        for result in results
    ) == 1
    assert len(repositories.accounts.accounts) == 1
    assert len(repositories.sessions.sessions) == 1


@pytest.mark.asyncio
async def test_login_creates_session_without_selecting_character() -> None:
    service, repositories = await auth_service()

    tokens = await service.login(
        'hero',
        'password',
        ip_address='127.0.0.1',
        user_agent='test-agent',
    )
    access_payload = service.authenticate_access_token(tokens.access_token)
    access_claims = jwt.decode(
        tokens.access_token,
        options={'verify_signature': False},
    )
    refresh_claims = jwt.decode(
        tokens.refresh_token,
        options={'verify_signature': False},
    )
    session = repositories.sessions.sessions[access_payload.session_id]

    assert isinstance(access_payload.account_id, UUID)
    assert access_claims['sub'] == str(access_payload.account_id)
    assert access_claims['account_id'] == str(access_payload.account_id)
    assert 'character_id' not in access_claims
    assert 'character_id' not in refresh_claims
    assert access_claims['session_id'] == str(access_payload.session_id)
    assert access_claims['token_type'] == 'access'
    assert refresh_claims['token_type'] == 'refresh'
    assert tokens.expires_in == 3 * 24 * 60 * 60
    assert session.ip_address == '127.0.0.1'
    assert session.user_agent == 'test-agent'
    assert session.active_character_id is None
    assert session.refresh_token_hash not in tokens.refresh_token


@pytest.mark.asyncio
async def test_login_without_character_succeeds_with_empty_game_context() -> None:
    service, repositories = await empty_auth_service()
    await service.register(
        'new-hero',
        'password',
        ip_address=None,
        user_agent=None,
    )

    tokens = await service.login(
        'new-hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    payload = service.authenticate_access_token(tokens.access_token)

    assert repositories.sessions.sessions[
        payload.session_id
    ].active_character_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('login', 'password'),
    [
        ('unknown', 'password'),
        ('hero', 'wrong'),
    ],
)
async def test_login_rejects_invalid_credentials(
    login: str,
    password: str,
) -> None:
    service, _ = await auth_service()

    with pytest.raises(InvalidCredentialsError):
        await service.login(
            login,
            password,
            ip_address=None,
            user_agent=None,
        )


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_preserves_game_context() -> None:
    service, repositories = await auth_service()
    tokens = await service.login(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    payload = service.authenticate_access_token(tokens.access_token)
    active_character_id = repositories.sessions.sessions[
        payload.session_id
    ].active_character_id

    refreshed_tokens = await service.refresh(tokens.refresh_token)
    refreshed_payload = service.authenticate_access_token(
        refreshed_tokens.access_token,
    )

    assert refreshed_tokens.refresh_token != tokens.refresh_token
    assert refreshed_payload == payload
    assert repositories.sessions.sessions[
        payload.session_id
    ].active_character_id == active_character_id
    with pytest.raises(InvalidTokenError):
        await service.refresh(tokens.refresh_token)


@pytest.mark.asyncio
async def test_concurrent_refresh_allows_only_one_rotation() -> None:
    service, _ = await auth_service()
    tokens = await service.login(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )

    results = await asyncio.gather(
        service.refresh(tokens.refresh_token),
        service.refresh(tokens.refresh_token),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, InvalidTokenError) for result in results) == 1


@pytest.mark.asyncio
async def test_deleted_or_expired_session_cannot_be_refreshed() -> None:
    service, repositories = await auth_service()
    deleted_tokens = await service.login(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    deleted_payload = service.authenticate_access_token(
        deleted_tokens.access_token,
    )
    await service.logout(deleted_payload.session_id)

    with pytest.raises(InvalidTokenError):
        await service.refresh(deleted_tokens.refresh_token)

    expired_tokens = await service.login(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    expired_payload = service.authenticate_access_token(
        expired_tokens.access_token,
    )
    repositories.sessions.sessions[expired_payload.session_id].expires_at = (
        datetime.now(UTC) - timedelta(seconds=1)
    )

    with pytest.raises(InvalidTokenError):
        await service.refresh(expired_tokens.refresh_token)


@pytest.mark.asyncio
async def test_logout_is_idempotent_and_access_remains_stateless() -> None:
    service, _ = await auth_service()
    tokens = await service.login(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    payload = service.authenticate_access_token(tokens.access_token)

    await service.logout(payload.session_id)
    await service.logout(payload.session_id)

    assert service.authenticate_access_token(tokens.access_token) == payload
    with pytest.raises(InvalidTokenError):
        await service.refresh(tokens.refresh_token)


@pytest.mark.asyncio
async def test_token_types_cannot_be_interchanged() -> None:
    service, _ = await auth_service()
    tokens = await service.login(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )

    with pytest.raises(InvalidTokenError):
        service.authenticate_access_token(tokens.refresh_token)

    with pytest.raises(InvalidTokenError):
        await service.refresh(tokens.access_token)


@pytest.mark.asyncio
async def test_invalid_signature_is_rejected() -> None:
    service, _ = await auth_service()
    tokens = await service.login(
        'hero',
        'password',
        ip_address=None,
        user_agent=None,
    )
    other_config = auth_config(
        secret_key='another-test-secret-with-at-least-32-bytes',
    )
    other_service = AuthService(
        other_config,
        FakeAuthRepositories(None, uuid7()),
        PasswordHasher(other_config),
    )

    with pytest.raises(InvalidTokenError):
        other_service.authenticate_access_token(tokens.access_token)

import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

from fastapi.testclient import TestClient

from app.application import create_app
from app.core.config import AdminPanelConfig, AppConfig, AuthConfig, DbConfig, LogConfig
from app.lifespans import db
from app.modules.auth.models import Account
from app.modules.auth.passwords import PasswordHasher
from app.modules.auth.service import AuthService
from app.modules.battles.enums import FightStatus
from app.modules.battles.models import Fight
from app.modules.characters.exceptions import InvalidGameSessionError
from app.modules.characters.service import CharacterService
from tests.modules.auth.fakes import FakeAuthRepositories


def build_auth_application(
    monkeypatch: object,
) -> tuple[object, AuthService, FakeAuthRepositories]:
    pool = Mock()
    monkeypatch.setattr(db, 'create_db_pool', AsyncMock(return_value=pool))
    monkeypatch.setattr(db, 'close_db_pool', AsyncMock())
    auth_config = AuthConfig(
        _env_file=None,
        secret_key='test-secret-key-with-at-least-32-bytes',
        password_salt='test-static-password-salt',
    )
    password_hasher = PasswordHasher(auth_config)
    account = Account(
        login='hero',
        password_hash=asyncio.run(password_hasher.hash('password')),
    )
    repositories = FakeAuthRepositories(account, uuid7())
    auth_service = AuthService(
        auth_config,
        repositories,
        password_hasher,
    )
    application = create_app(
        app_config=AppConfig(_env_file=None),
        admin_config=AdminPanelConfig(_env_file=None, enabled=False),
        auth_config=auth_config,
        db_config=DbConfig(_env_file=None),
        log_config=LogConfig(_env_file=None),
    )
    return application, auth_service, repositories


def test_register_returns_tokens_and_rejects_existing_login(
    monkeypatch: object,
) -> None:
    application, auth_service, repositories = build_auth_application(
        monkeypatch,
    )
    with TestClient(application) as client:
        application.state.auth_service = auth_service
        application.state.character_service = CharacterService(repositories)
        register_response = client.post(
            '/api/v1/auth/register',
            json={'login': 'new-hero', 'password': 'new-password'},
        )
        assert register_response.status_code == 201
        registered_tokens = register_response.json()
        registered_payload = auth_service.authenticate_access_token(
            registered_tokens['access_token'],
        )
        registered_account = repositories.accounts.accounts['new-hero']
        assert registered_payload.account_id == registered_account.id
        assert repositories.sessions.sessions[
            registered_payload.session_id
        ].ip_address == 'testclient'

        conflict_response = client.post(
            '/api/v1/auth/register',
            json={'login': 'new-hero', 'password': 'other-password'},
        )
        assert conflict_response.status_code == 409
        assert conflict_response.json() == {
            'detail': 'User with this login already exists',
        }


        list_response = client.get(
            '/api/v1/characters',
            headers={
                'Authorization': f'Bearer {registered_tokens["access_token"]}',
            },
        )
        assert list_response.status_code == 200
        assert list_response.json() == []

        create_character_response = client.post(
            '/api/v1/characters',
            headers={
                'Authorization': f'Bearer {registered_tokens["access_token"]}',
            },
            json={'nickname': 'NewHero'},
        )
        assert create_character_response.status_code == 201
        assert create_character_response.json()['is_active']

        select_character_response = client.post(
            f'/api/v1/characters/{create_character_response.json()["id"]}/select',
            headers={
                'Authorization': f'Bearer {registered_tokens["access_token"]}',
            },
        )
        assert select_character_response.status_code == 200
        assert select_character_response.json() == create_character_response.json()

        missing_character_response = client.post(
            f'/api/v1/characters/{uuid7()}/select',
            headers={
                'Authorization': f'Bearer {registered_tokens["access_token"]}',
            },
        )
        assert missing_character_response.status_code == 404
        assert missing_character_response.json() == {
            'detail': 'character_not_found',
        }

        duplicate_character_response = client.post(
            '/api/v1/characters',
            headers={
                'Authorization': f'Bearer {registered_tokens["access_token"]}',
            },
            json={'nickname': 'AnotherHero'},
        )
        assert duplicate_character_response.status_code == 409
        assert duplicate_character_response.json() == {
            'detail': 'character_already_exists',
        }


def test_authentication_refresh_and_protected_fight_endpoint(
    monkeypatch: object,
) -> None:
    application, auth_service, repositories = build_auth_application(
        monkeypatch,
    )
    with TestClient(application) as client:
        application.state.auth_service = auth_service
        application.state.character_service = CharacterService(repositories)
        login_response = client.post(
            '/api/v1/auth/login',
            json={'login': 'hero', 'password': 'password'},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        assert tokens['token_type'] == 'bearer'
        token_payload = auth_service.authenticate_access_token(
            tokens['access_token'],
        )
        session = repositories.sessions.sessions[token_payload.session_id]
        assert session.ip_address == 'testclient'
        assert session.user_agent == 'testclient'

        refresh_response = client.post(
            '/api/v1/auth/refresh',
            json={'refresh_token': tokens['refresh_token']},
        )
        assert refresh_response.status_code == 200
        refreshed_tokens = refresh_response.json()
        assert refreshed_tokens['access_token'] != tokens['access_token']
        assert refreshed_tokens['refresh_token'] != tokens['refresh_token']
        assert client.post(
            '/api/v1/auth/refresh',
            json={'refresh_token': tokens['refresh_token']},
        ).status_code == 401

        target_id = uuid7()
        unauthorized_response = client.post(
            '/api/v1/fights',
            json={'target_id': str(target_id)},
        )
        assert unauthorized_response.status_code == 401

        wrong_token_response = client.post(
            '/api/v1/fights',
            headers={'Authorization': f'Bearer {tokens["refresh_token"]}'},
            json={'target_id': str(target_id)},
        )
        assert wrong_token_response.status_code == 401

        expected_fight = Fight(status=FightStatus.started)
        application.state.fight_service.create_fight = AsyncMock(return_value=expected_fight)
        response = client.post(
            '/api/v1/fights',
            headers={'Authorization': f'Bearer {tokens["access_token"]}'},
            json={'target_id': str(target_id)},
        )

        assert response.status_code == 201
        assert response.json()['id'] == str(expected_fight.id)
        application.state.fight_service.create_fight.assert_awaited_once_with(
            account_id=token_payload.account_id,
            session_id=token_payload.session_id,
            target_id=target_id,
        )

        logout_response = client.post(
            '/api/v1/auth/logout',
            headers={
                'Authorization': f'Bearer {refreshed_tokens["access_token"]}',
            },
        )
        assert logout_response.status_code == 204
        assert client.post(
            '/api/v1/auth/refresh',
            json={'refresh_token': refreshed_tokens['refresh_token']},
        ).status_code == 401

        application.state.fight_service.create_fight.side_effect = (
            InvalidGameSessionError
        )
        access_after_logout = client.post(
            '/api/v1/fights',
            headers={'Authorization': f'Bearer {tokens["access_token"]}'},
            json={'target_id': str(target_id)},
        )
        assert access_after_logout.status_code == 401
        assert access_after_logout.json() == {
            'detail': 'invalid_or_expired_session',
        }

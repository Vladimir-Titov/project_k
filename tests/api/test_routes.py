import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

from fastapi.testclient import TestClient

from app.api.dependencies import get_unit_of_work
from app.application import create_app
from app.core.config import AdminPanelConfig, AppConfig, AuthConfig, DbConfig, LogConfig
from app.lifespans import db
from app.modules.auth.models import Account
from app.modules.auth.passwords import PasswordHasher
from app.modules.auth.service import AuthService
from app.modules.battles.enums import FightStatus
from app.modules.battles.models import Fight
from app.modules.characters.exceptions import CharacterAlreadyExistsError, CharacterNotFoundError
from app.modules.game_context.exceptions import CharacterRequiredError
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
    auth_service = AuthService(auth_config, repositories, password_hasher)
    application = create_app(
        app_config=AppConfig(_env_file=None),
        admin_config=AdminPanelConfig(_env_file=None, enabled=False),
        auth_config=auth_config,
        db_config=DbConfig(_env_file=None),
        log_config=LogConfig(_env_file=None),
    )

    async def override_unit_of_work() -> AsyncIterator[FakeAuthRepositories]:
        async with repositories.transaction() as transaction:
            yield transaction

    application.dependency_overrides[get_unit_of_work] = override_unit_of_work
    return application, auth_service, repositories


def configure_battle_repositories(
    repositories: FakeAuthRepositories,
    *,
    target_id: object,
) -> Fight:
    expected_fight = Fight(status=FightStatus.started, title='Нападение на Target')
    repositories.fights = SimpleNamespace(create=AsyncMock(return_value=expected_fight))
    repositories.mobs = SimpleNamespace(
        get_by_id=AsyncMock(
            side_effect=lambda entity_id: SimpleNamespace(title='Target')
            if entity_id == target_id
            else None,
        ),
    )
    repositories.fight_participants = SimpleNamespace(create_many=AsyncMock())
    return expected_fight


def test_character_requires_explicit_selection_before_fight(monkeypatch: object) -> None:
    application, auth_service, repositories = build_auth_application(monkeypatch)
    with TestClient(application) as client:
        application.state.auth_service = auth_service
        register_response = client.post(
            '/api/v1/auth/register',
            json={'login': 'new-hero', 'password': 'new-password'},
        )
        assert register_response.status_code == 201
        tokens = register_response.json()
        headers = {'Authorization': f'Bearer {tokens["access_token"]}'}
        duplicate_register = client.post(
            '/api/v1/auth/register',
            json={'login': 'new-hero', 'password': 'other-password'},
        )
        assert duplicate_register.status_code == 409
        assert duplicate_register.json() == {
            'detail': 'User with this login already exists',
        }

        create_response = client.post(
            '/api/v1/characters',
            headers=headers,
            json={'nickname': 'NewHero'},
        )
        assert create_response.status_code == 201
        assert create_response.json()['is_active'] is False

        duplicate_character = client.post(
            '/api/v1/characters',
            headers=headers,
            json={'nickname': 'AnotherHero'},
        )
        assert duplicate_character.json() == {'detail': 'character_already_exists'}
        missing_character = client.post(
            f'/api/v1/characters/{uuid7()}/select',
            headers=headers,
        )
        assert missing_character.json() == {'detail': 'character_not_found'}

        target_id = uuid7()
        before_select = client.post(
            '/api/v1/fights',
            headers=headers,
            json={'target_id': str(target_id)},
        )
        assert before_select.status_code == 409
        assert before_select.json() == {'detail': 'character_required'}

        select_response = client.post(
            f'/api/v1/characters/{create_response.json()["id"]}/select',
            headers=headers,
        )
        assert select_response.status_code == 200
        assert select_response.json()['is_active'] is True

        expected_fight = configure_battle_repositories(
            repositories,
            target_id=target_id,
        )
        fight_response = client.post(
            '/api/v1/fights',
            headers=headers,
            json={'target_id': str(target_id)},
        )
        assert fight_response.status_code == 201
        assert fight_response.json()['id'] == str(expected_fight.id)

        session_payload = auth_service.authenticate_access_token(tokens['access_token'])
        assert repositories.sessions.for_update_values == [True] * 6
        assert repositories.transaction_entries == 7
        assert repositories.transaction_failures == [
            CharacterAlreadyExistsError,
            CharacterNotFoundError,
            CharacterRequiredError,
        ]
        assert str(
            repositories.sessions.sessions[session_payload.session_id].active_character_id,
        ) == create_response.json()['id']


def test_auth_errors_context_and_missing_fight_target(monkeypatch: object) -> None:
    application, auth_service, repositories = build_auth_application(monkeypatch)
    with TestClient(application) as client:
        application.state.auth_service = auth_service
        invalid_login = client.post(
            '/api/v1/auth/login',
            json={'login': 'hero', 'password': 'wrong'},
        )
        assert invalid_login.status_code == 401
        assert invalid_login.json() == {'detail': 'Incorrect login or password'}

        login_response = client.post(
            '/api/v1/auth/login',
            json={'login': 'hero', 'password': 'password'},
        )
        tokens = login_response.json()
        payload = auth_service.authenticate_access_token(tokens['access_token'])
        assert repositories.sessions.sessions[payload.session_id].active_character_id is None

        refresh_response = client.post(
            '/api/v1/auth/refresh',
            json={'refresh_token': tokens['refresh_token']},
        )
        assert refresh_response.status_code == 200
        assert client.post(
            '/api/v1/auth/refresh',
            json={'refresh_token': tokens['refresh_token']},
        ).json() == {'detail': 'Invalid or expired refresh token'}

        assert client.post('/api/v1/fights', json={'target_id': str(uuid7())}).json() == {
            'detail': 'Not authenticated',
        }
        wrong_type = client.post(
            '/api/v1/fights',
            headers={'Authorization': f'Bearer {tokens["refresh_token"]}'},
            json={'target_id': str(uuid7())},
        )
        assert wrong_type.json() == {'detail': 'Invalid or expired access token'}

        character = next(iter(repositories.characters.characters.values()))
        headers = {'Authorization': f'Bearer {tokens["access_token"]}'}
        assert client.post(
            f'/api/v1/characters/{character.id}/select',
            headers=headers,
        ).status_code == 200

        configure_battle_repositories(repositories, target_id=uuid7())
        missing_target = client.post(
            '/api/v1/fights',
            headers=headers,
            json={'target_id': str(uuid7())},
        )
        assert missing_target.status_code == 404
        assert missing_target.json() == {'detail': 'fight_target_not_found'}

        logout_response = client.post('/api/v1/auth/logout', headers=headers)
        assert logout_response.status_code == 204
        after_logout = client.post(
            '/api/v1/fights',
            headers=headers,
            json={'target_id': str(uuid7())},
        )
        assert after_logout.status_code == 401
        assert after_logout.json() == {'detail': 'invalid_or_expired_session'}

from unittest.mock import AsyncMock, Mock
from uuid import uuid7

from fastapi.testclient import TestClient

from app.enums.fights import FightStatus
from app.models.fights import Fight
from settings import AdminPanelConfig, AppConfig, AuthConfig, DbConfig, LogConfig
from web.create_app import create_app
from web.lifespans import db


def test_authentication_refresh_and_protected_fight_endpoint(monkeypatch: object) -> None:
    pool = Mock()
    monkeypatch.setattr(db, 'create_db_pool', AsyncMock(return_value=pool))
    monkeypatch.setattr(db, 'close_db_pool', AsyncMock())
    application = create_app(
        app_config=AppConfig(_env_file=None),
        admin_config=AdminPanelConfig(_env_file=None, enabled=False),
        auth_config=AuthConfig(
            _env_file=None,
            secret_key='test-secret-key-with-at-least-32-bytes',
        ),
        db_config=DbConfig(_env_file=None),
        log_config=LogConfig(_env_file=None),
    )

    with TestClient(application) as client:
        login_response = client.post(
            '/api/v1/auth/login',
            json={'login': 'hero', 'password': 'password'},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        assert tokens['token_type'] == 'bearer'

        refresh_response = client.post(
            '/api/v1/auth/refresh',
            json={'refresh_token': tokens['refresh_token']},
        )
        assert refresh_response.status_code == 200
        assert refresh_response.json()['access_token'] != tokens['access_token']

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
        application.state.services.create_fight = AsyncMock(return_value=expected_fight)
        token_payload = application.state.services.auth.authenticate_access_token(tokens['access_token'])
        response = client.post(
            '/api/v1/fights',
            headers={'Authorization': f'Bearer {tokens["access_token"]}'},
            json={'target_id': str(target_id)},
        )

        assert response.status_code == 201
        assert response.json()['id'] == str(expected_fight.id)
        application.state.services.create_fight.assert_awaited_once_with(
            attacker_id=token_payload.character_id,
            target_id=target_id,
        )

from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from app.application import create_app
from app.core.config import AdminPanelConfig, AppConfig, DbConfig, LogConfig
from app.lifespans import db


def test_lifespan_exposes_pool_and_closes_it(monkeypatch: object) -> None:
    pool = Mock()
    create_pool = AsyncMock(return_value=pool)
    close_pool = AsyncMock()
    monkeypatch.setattr(db, 'create_db_pool', create_pool)
    monkeypatch.setattr(db, 'close_db_pool', close_pool)
    db_config = DbConfig(_env_file=None, pool_close_timeout=3)
    application = create_app(
        app_config=AppConfig(_env_file=None),
        admin_config=AdminPanelConfig(_env_file=None, enabled=False),
        db_config=db_config,
        log_config=LogConfig(_env_file=None),
    )

    with TestClient(application) as client:
        assert client.app.state.db_pool is pool
        assert client.app.state.repositories.pool is pool
        assert client.app.state.fight_service.repositories is client.app.state.repositories
        assert client.app.state.auth_service is not None
        assert client.app.state.character_service is not None
        assert client.get('/').json() == {'message': 'Hello World'}

    create_pool.assert_awaited_once_with(db_config)
    close_pool.assert_awaited_once_with(pool, 3)
    assert not hasattr(application.state, 'db_pool')
    assert not hasattr(application.state, 'repositories')
    assert not hasattr(application.state, 'fight_service')
    assert not hasattr(application.state, 'auth_service')
    assert not hasattr(application.state, 'character_service')


def test_cors_wildcard_preflight(monkeypatch: object) -> None:
    pool = Mock()
    monkeypatch.setattr(db, 'create_db_pool', AsyncMock(return_value=pool))
    monkeypatch.setattr(db, 'close_db_pool', AsyncMock())
    application = create_app(
        app_config=AppConfig(_env_file=None, cors_origins=['*']),
        admin_config=AdminPanelConfig(_env_file=None, enabled=False),
        db_config=DbConfig(_env_file=None),
        log_config=LogConfig(_env_file=None),
    )

    with TestClient(application) as client:
        response = client.options(
            '/',
            headers={
                'Origin': 'https://frontend.example',
                'Access-Control-Request-Method': 'GET',
            },
        )

    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == '*'
    assert 'access-control-allow-credentials' not in response.headers

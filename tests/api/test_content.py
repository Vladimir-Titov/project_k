from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_unit_of_work
from app.application import create_app
from app.core.config import AdminPanelConfig, AppConfig, DbConfig, LogConfig, StorageConfig
from app.lifespans import db
from app.modules.content.models import ActionDefinition, EffectDefinition


@pytest.mark.parametrize(
    ('path', 'repository_name', 'model', 'fields'),
    (
        ('/api/v1/action-definitions', 'action_definitions', ActionDefinition, {'target_policy': 'enemy'}),
        (
            '/api/v1/effect-definitions',
            'effect_definitions',
            EffectDefinition,
            {'duration': 'turns', 'duration_turns': 2},
        ),
    ),
)
def test_definition_api_returns_image_urls_and_allows_missing_images(monkeypatch, path, repository_name, model, fields):
    image_url = 'https://assets.example.com/icons/test.png'
    definitions = [
        model(code='with_image', title='With image', image_url=image_url, **fields),
        model(code='without_image', title='Without image', **fields),
    ]
    repository = SimpleNamespace(search=AsyncMock(return_value=definitions))
    repositories = SimpleNamespace(**{repository_name: repository})
    monkeypatch.setattr(db, 'create_db_pool', AsyncMock(return_value=Mock()))
    monkeypatch.setattr(db, 'close_db_pool', AsyncMock())
    application = create_app(
        app_config=AppConfig(_env_file=None),
        admin_config=AdminPanelConfig(_env_file=None, enabled=False),
        db_config=DbConfig(_env_file=None),
        log_config=LogConfig(_env_file=None),
        storage_config=StorageConfig(_env_file=None, enabled=False),
    )
    application.dependency_overrides[get_unit_of_work] = lambda: repositories

    with TestClient(application) as client:
        response = client.get(path)

    assert response.status_code == 200
    rows = response.json()
    assert [(row['code'], row['image_url']) for row in rows] == [
        ('with_image', image_url),
        ('without_image', None),
    ]
    assert [row['id'] for row in rows] == [str(definition.id) for definition in definitions]
    repository.search.assert_awaited_once_with(is_active=True, is_archived=False, order_by='code')

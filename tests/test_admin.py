from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette_admin.fields import HasMany, HasOne, PasswordField

from app.models import Account, Fight
from settings import AdminPanelConfig, AppConfig, AuthConfig, DbConfig, LogConfig
from web.admin.views import AccountAdmin, FightAdmin, create_admin_views
from web.create_app import create_app
from web.lifespans import db


def build_app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    admin_enabled: bool,
):
    pool = Mock()
    monkeypatch.setattr(db, 'create_db_pool', AsyncMock(return_value=pool))
    monkeypatch.setattr(db, 'close_db_pool', AsyncMock())
    return create_app(
        app_config=AppConfig(_env_file=None),
        admin_config=AdminPanelConfig(
            _env_file=None,
            enabled=admin_enabled,
            login='staff',
            password='staff-password',
            session_secret='test-admin-session-secret-at-least-32-bytes',
        ),
        auth_config=AuthConfig(_env_file=None),
        db_config=DbConfig(_env_file=None),
        log_config=LogConfig(_env_file=None),
    )


def test_admin_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    application = build_app(monkeypatch, admin_enabled=False)

    with TestClient(application) as client:
        assert client.get('/admin/').status_code == 404
        assert not hasattr(application.state, 'admin_engine')


def test_admin_requires_valid_session_login(monkeypatch: pytest.MonkeyPatch) -> None:
    application = build_app(monkeypatch, admin_enabled=True)

    with TestClient(application) as client:
        assert client.get('/admin/', follow_redirects=False).status_code == 303
        invalid = client.post(
            '/admin/login',
            data={'username': 'staff', 'password': 'wrong'},
            follow_redirects=False,
        )
        assert invalid.status_code == 400

        login = client.post(
            '/admin/login',
            data={'username': 'staff', 'password': 'staff-password'},
            follow_redirects=False,
        )
        assert login.status_code == 303
        assert client.get('/admin/').status_code == 200

        client.get('/admin/logout')
        assert client.get('/admin/', follow_redirects=False).status_code == 303

    assert not hasattr(application.state, 'admin_engine')


def test_admin_registers_all_models_and_relationship_fields() -> None:
    views = create_admin_views()

    assert len(views) == 9
    assert {view.model for view in views} >= {Account, Fight}
    assert all(view.pk_attr in view.sortable_fields for view in views)
    assert all(
        all(field_name in view.sortable_fields for field_name, _descending in view.fields_default_sort)
        for view in views
    )
    account_view = next(view for view in views if isinstance(view, AccountAdmin))
    password_field = next(field for field in account_view.fields if field.name == 'password')
    assert isinstance(password_field, PasswordField)
    assert password_field.exclude_from_list
    assert password_field.exclude_from_detail

    fight_view = next(view for view in views if isinstance(view, FightAdmin))
    relationship_fields = {field.name: field for field in fight_view.fields if isinstance(field, (HasOne, HasMany))}
    assert isinstance(relationship_fields['participants'], HasMany)
    assert isinstance(relationship_fields['actions'], HasMany)


class FakeAsyncSession(AsyncSession):
    def __init__(self) -> None:
        super().__init__()
        self.added: list[object] = []
        self.committed = False

    def add(self, instance: object, *, _warn: bool = True) -> None:
        del _warn
        self.added.append(instance)

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_admin_delete_archives_instead_of_removing() -> None:
    view = FightAdmin(Fight)
    fight = Fight()
    view.find_by_pks = AsyncMock(return_value=[fight])
    session = FakeAsyncSession()
    request = SimpleNamespace(state=SimpleNamespace(session=session))

    deleted_count = await view.delete(request, [fight.id])

    assert deleted_count == 1
    assert fight.is_archived
    assert session.added == [fight]
    assert session.committed


@pytest.mark.asyncio
async def test_select2_representation_is_visible_html_and_escaped() -> None:
    view = AccountAdmin(Account)
    account = Account(login='<staff>', password='password')

    representation = await view.select2_result(account, SimpleNamespace())

    assert representation == '<span>&lt;staff&gt;</span>'

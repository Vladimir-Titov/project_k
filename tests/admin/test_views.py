from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.pool import StaticPool
from starlette.applications import Starlette
from starlette_admin._types import RequestAction
from starlette_admin.contrib.sqla import Admin
from starlette_admin.fields import PasswordField, RelationField

from app.admin.views import AccountAdmin, FightAdmin, create_admin_views
from app.application import create_app
from app.core.config import AdminPanelConfig, AppConfig, AuthConfig, DbConfig, LogConfig, StorageConfig
from app.core.files.images import ImageService
from app.core.files.repository import FileStorageError
from app.lifespans import db
from app.modules.auth.models import Account, Session
from app.modules.auth.passwords import PasswordHasher
from app.modules.battles.models import (
    Fight,
    FightAction,
    FightActiveEffect,
    FightEvent,
    FightParticipants,
    FightParticipantStat,
)
from app.modules.bots.models import BotTemplate, BotTemplateAction, BotTemplateStat
from app.modules.characters.models import (
    Character,
    CharacterAction,
    CharacterClass,
    CharacterStat,
    ClassAction,
    ClassStat,
)
from app.modules.content.models import ActionDefinition, ActionEffect, EffectDefinition, EffectRule
from app.modules.stats.enums import StatKind
from app.modules.stats.models import StatDefinition


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
        storage_config=StorageConfig(_env_file=None, enabled=False),
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
    password_hasher = PasswordHasher(AuthConfig(_env_file=None))
    views = create_admin_views(password_hasher)

    expected_models = {
        Account,
        Session,
        Character,
        Fight,
        FightParticipants,
        BotTemplate,
        BotTemplateStat,
        BotTemplateAction,
        CharacterClass,
        StatDefinition,
        ClassStat,
        CharacterStat,
        ActionDefinition,
        EffectDefinition,
        EffectRule,
        ActionEffect,
        ClassAction,
        CharacterAction,
        FightParticipantStat,
        FightActiveEffect,
        FightAction,
        FightEvent,
    }
    assert len(views) == len(expected_models)
    assert {view.model for view in views} == expected_models
    assert all(view.pk_attr in view.sortable_fields for view in views)
    assert all(
        all(field_name in view.sortable_fields for field_name, _descending in view.fields_default_sort)
        for view in views
    )
    account_view = next(view for view in views if isinstance(view, AccountAdmin))
    password_field = next(field for field in account_view.fields if field.name == 'password_hash')
    assert isinstance(password_field, PasswordField)
    assert password_field.exclude_from_list
    assert password_field.exclude_from_detail


@pytest.fixture
def content_admin():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS frontiers")
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS auth")
        ClassStat.metadata.create_all(connection)
    with DbSession(engine) as session:
        character_class = CharacterClass(code='warrior', title='Warrior')
        stat = StatDefinition(code='health', title='Health', kind=StatKind.RESOURCE)
        class_stat = ClassStat(value=100, character_class=character_class, stat_definition=stat)
        session.add(class_stat)
        session.commit()
        class_stat_id, class_id, stat_id = class_stat.id, character_class.id, stat.id
    admin = Admin(engine)
    views = create_admin_views(PasswordHasher(AuthConfig(_env_file=None)))
    for view in views:
        admin.add_view(view)
    application = Starlette()
    admin.mount_to(application)
    with TestClient(application) as client:
        yield client, engine, views, class_stat_id, class_id, stat_id
    engine.dispose()


def test_class_stats_list_shows_related_names_and_keeps_detail_ids(content_admin) -> None:
    client, _engine, views, class_stat_id, _class_id, _stat_id = content_admin
    response = client.get('/admin/api/class-stat')

    assert response.status_code == 200
    row = response.json()['items'][0]
    assert row['character_class']['_meta']['repr'] == 'Warrior (warrior)'
    assert row['stat_definition']['_meta']['repr'] == 'Health (health)'
    assert Decimal(row['value']) == 100
    view = next(view for view in views if view.model is ClassStat)
    fields = view.get_fields_list(SimpleNamespace(), RequestAction.LIST)
    assert [field.name for field in fields] == ['character_class', 'stat_definition', 'value', 'is_archived']
    assert all(isinstance(field, RelationField) for field in fields[:2])
    detail_fields = view.get_fields_list(SimpleNamespace(), RequestAction.DETAIL)
    assert {'id', 'created_at', 'updated_at'} <= {field.name for field in detail_fields}
    assert client.get(f'/admin/class-stat/detail/{class_stat_id}').status_code == 200


def test_bot_links_show_shared_stat_and_action_names(content_admin) -> None:
    client, engine, views, _class_stat_id, _class_id, stat_id = content_admin
    with DbSession(engine) as session:
        template = BotTemplate(code='bandit', title='Bandit')
        definition = session.get(StatDefinition, stat_id)
        action = ActionDefinition(code='basic_attack', title='Basic attack', target_policy='enemy')
        session.add_all(
            [
                BotTemplateStat(bot_template=template, stat_definition=definition, value=65),
                BotTemplateAction(bot_template=template, action_definition=action, priority=0),
            ],
        )
        session.commit()

    stat_row = client.get('/admin/api/bot-template-stat').json()['items'][0]
    action_row = client.get('/admin/api/bot-template-action').json()['items'][0]
    template_options = client.get(
        '/admin/api/bot-template',
        params={'select2': 'true', 'where': 'bandit', 'order_by': 'id asc'},
    )
    assert template_options.status_code == 200
    assert [item['code'] for item in template_options.json()['items']] == ['bandit']
    assert stat_row['bot_template']['_meta']['repr'] == 'Bandit (bandit)'
    assert stat_row['stat_definition']['_meta']['repr'] == 'Health (health)'
    assert action_row['action_definition']['_meta']['repr'] == 'Basic attack (basic_attack)'
    stat_view = next(view for view in views if view.model is BotTemplateStat)
    fields = stat_view.get_fields_list(SimpleNamespace(), RequestAction.LIST)
    assert [field.name for field in fields] == ['bot_template', 'stat_definition', 'value', 'is_archived']


def test_bot_stat_can_be_created_with_template_from_relation_select(content_admin) -> None:
    client, engine, _views, _class_stat_id, _class_id, stat_id = content_admin
    with DbSession(engine) as session:
        template = BotTemplate(code='bear', title='Bear')
        session.add(template)
        session.commit()
        template_id = template.id

    form = client.get('/admin/bot-template-stat/create')
    assert form.status_code == 200
    assert 'data-url="http://testserver/admin/api/bot-template"' in form.text
    options = client.get(
        '/admin/api/bot-template',
        params={'select2': 'true', 'where': '', 'order_by': 'id asc'},
    )
    assert options.status_code == 200
    assert [item['code'] for item in options.json()['items']] == ['bear']

    response = client.post(
        '/admin/bot-template-stat/create',
        data={'bot_template': str(template_id), 'stat_definition': str(stat_id), 'value': '42'},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with DbSession(engine) as session:
        bot_stat = session.query(BotTemplateStat).one()
        assert bot_stat.bot_template_id == template_id
        assert bot_stat.stat_definition_id == stat_id
        assert bot_stat.value == 42


def test_class_stat_can_be_edited_by_selecting_related_entities(content_admin) -> None:
    client, engine, _views, class_stat_id, class_id, _stat_id = content_admin
    with DbSession(engine) as session:
        stat = StatDefinition(code='strength', title='Strength', kind=StatKind.ATTRIBUTE)
        session.add(stat)
        session.commit()
        stat_id = stat.id
    response = client.post(
        f'/admin/class-stat/edit/{class_stat_id}',
        data={'character_class': str(class_id), 'stat_definition': str(stat_id), 'value': '12'},
        follow_redirects=False,
    )

    assert response.status_code == 303
    with DbSession(engine) as session:
        class_stat = session.get(ClassStat, class_stat_id)
        assert class_stat.class_id == class_id
        assert class_stat.stat_definition_id == stat_id
        assert class_stat.value == 12


def test_hidden_dates_keep_default_sort_without_overriding_user_sort(content_admin) -> None:
    client, engine, _views, class_stat_id, class_id, _stat_id = content_admin
    with DbSession(engine) as session:
        session.get(ClassStat, class_stat_id).created_at = datetime(2020, 1, 1, tzinfo=UTC)
        stat = StatDefinition(code='strength', title='Strength', kind=StatKind.ATTRIBUTE)
        session.add(ClassStat(class_id=class_id, stat_definition=stat, value=12, is_archived=True))
        session.commit()

    rows = client.get('/admin/api/class-stat').json()['items']
    assert [row['stat_definition']['code'] for row in rows] == ['strength', 'health']
    rows = client.get('/admin/api/class-stat', params={'order_by': 'is_archived asc'}).json()['items']
    assert [row['stat_definition']['code'] for row in rows] == ['health', 'strength']


@pytest.mark.parametrize(
    ('model', 'fields'),
    (
        (ActionDefinition, {'target_policy': 'enemy'}),
        (EffectDefinition, {'duration': 'turns', 'duration_turns': 2, 'stacking_policy': 'refresh'}),
    ),
)
def test_definition_images_can_be_edited_in_admin(content_admin, model, fields) -> None:
    client, engine, views, _class_stat_id, _class_id, _stat_id = content_admin
    with DbSession(engine) as session:
        definition = model(code='test', title='Test', **fields)
        session.add(definition)
        session.commit()
        definition_id = definition.id
    view = next(view for view in views if view.model is model)
    image_url = 'https://assets.example.com/icons/test.png'

    response = client.post(
        f'/admin/{view.identity}/edit/{definition_id}',
        data={'code': 'test', 'title': 'Test', 'image_url': image_url, 'is_active': 'on', **fields},
        follow_redirects=False,
    )

    assert response.status_code == 303
    with DbSession(engine) as session:
        assert session.get(model, definition_id).image_url == image_url
    rows = client.get(f'/admin/api/{view.identity}').json()['items']
    assert rows[0]['image_url'] == image_url


@pytest.fixture
def image_admin(content_admin):
    client, engine, views, *_ = content_admin
    files = Mock()
    files.put = AsyncMock()
    files.public_url.side_effect = lambda key: f'http://localhost:9000/project-k/{key}'
    images = ImageService(files, max_size_bytes=1024)
    for view in views:
        if view.model in (ActionDefinition, EffectDefinition):
            view.images = images
    buffer = BytesIO()
    Image.new('RGB', (2, 2), 'red').save(buffer, format='PNG')
    return client, engine, files, buffer.getvalue()


@pytest.mark.parametrize(
    ('model', 'identity', 'fields'),
    (
        (ActionDefinition, 'action-definition', {'target_policy': 'enemy'}),
        (
            EffectDefinition,
            'effect-definition',
            {'duration': 'turns', 'duration_turns': '2', 'stacking_policy': 'refresh'},
        ),
    ),
)
def test_admin_image_upload_create_keep_replace_and_remove(image_admin, model, identity, fields) -> None:
    client, engine, files, image_data = image_admin
    form = {'code': 'uploaded', 'title': 'Uploaded', 'is_active': 'on', **fields}
    response = client.post(
        f'/admin/{identity}/create',
        data=form,
        files={'image_upload': ('fake-name.txt', image_data, 'text/plain')},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    row = client.get(f'/admin/api/{identity}').json()['items'][0]
    original_url = row['image_url']
    assert original_url.startswith('http://localhost:9000/project-k/images/')
    assert original_url.endswith('.png')
    assert row['image_upload'] == {'url': original_url}
    assert files.put.call_args.args[1:] == (image_data, 'image/png')
    edit_url = f'/admin/{identity}/edit/{row["id"]}'
    assert original_url in client.get(edit_url).text
    assert original_url in client.get(f'/admin/{identity}/detail/{row["id"]}').text

    response = client.post(edit_url, data={**form, 'image_url': original_url}, follow_redirects=False)
    assert response.status_code == 303
    assert client.get(f'/admin/api/{identity}').json()['items'][0]['image_url'] == original_url
    files.put.assert_awaited_once()

    response = client.post(
        edit_url,
        data={**form, 'image_url': original_url},
        files={'image_upload': ('second.png', image_data, 'image/png')},
        follow_redirects=False,
    )
    assert response.status_code == 303
    replacement_url = client.get(f'/admin/api/{identity}').json()['items'][0]['image_url']
    assert replacement_url != original_url
    assert files.put.await_count == 2

    response = client.post(
        edit_url,
        data={**form, 'image_url': replacement_url, '_image_upload-delete': 'on'},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with DbSession(engine) as session:
        assert session.get(model, UUID(row['id'])).image_url is None
    files.delete.assert_not_called()


@pytest.mark.parametrize('failure', ['invalid', 'oversize', 'storage', 'disabled'])
def test_failed_image_upload_keeps_existing_definition(image_admin, content_admin, failure) -> None:
    client, engine, files, image_data = image_admin
    with DbSession(engine) as session:
        definition = ActionDefinition(
            code='test',
            title='Original',
            target_policy='enemy',
            image_url='https://example.com/old.png',
        )
        session.add(definition)
        session.commit()
        pk = definition.id
    error_text = 'not a valid image'
    if failure == 'invalid':
        image_data = b'<script>not an image</script>'
    elif failure == 'oversize':
        image_data = b'x' * 1025
        error_text = 'must not exceed'
    elif failure == 'storage':
        files.put.side_effect = FileStorageError('Storage is unavailable')
        error_text = 'Storage is unavailable'
    else:
        for view in content_admin[2]:
            if view.model is ActionDefinition:
                view.images = None
        error_text = 'uploads are disabled'
    response = client.post(
        f'/admin/action-definition/edit/{pk}',
        data={'code': 'test', 'title': 'Changed', 'target_policy': 'enemy', 'image_url': 'https://example.com/old.png'},
        files={'image_upload': ('image.png', image_data, 'image/png')},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert error_text in response.text
    with DbSession(engine) as session:
        definition = session.get(ActionDefinition, pk)
        assert definition.title == 'Original'
        assert definition.image_url == 'https://example.com/old.png'
    if failure != 'storage':
        files.put.assert_not_awaited()


def test_snapshot_relationships_are_visible_but_cannot_be_edited() -> None:
    views = create_admin_views(PasswordHasher(AuthConfig(_env_file=None)))
    for model, relation_names, id_names in (
        (Fight, {'active_participant', 'winner_participant'}, {'active_participant_id', 'winner_participant_id'}),
        (FightParticipantStat, {'stat_definition'}, {'stat_definition_id'}),
    ):
        view = next(view for view in views if view.model is model)
        request = SimpleNamespace()
        list_names = {field.name for field in view.get_fields_list(request, RequestAction.LIST)}
        assert relation_names <= list_names
        assert not id_names & list_names
        for action in (RequestAction.CREATE, RequestAction.EDIT):
            assert not relation_names & {field.name for field in view.get_fields_list(request, action)}


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
    view = AccountAdmin(
        Account,
        PasswordHasher(AuthConfig(_env_file=None)),
    )
    account = Account(login='<staff>', password_hash='password-hash')

    representation = await view.select2_result(account, SimpleNamespace())

    assert representation == '<span>&lt;staff&gt;</span>'


@pytest.mark.asyncio
async def test_account_admin_hashes_plain_password_before_create() -> None:
    password_hasher = Mock()
    password_hasher.hash = AsyncMock(return_value='$argon2id$stored-hash')
    view = AccountAdmin(Account, password_hasher)
    account = Account(login='hero', password_hash='plain-password')

    await view.before_create(
        SimpleNamespace(),
        {'password_hash': 'plain-password'},
        account,
    )

    assert account.password_hash == '$argon2id$stored-hash'
    password_hasher.hash.assert_awaited_once_with('plain-password')


@pytest.mark.asyncio
async def test_account_admin_keeps_hash_when_edit_password_is_blank() -> None:
    password_hasher = Mock()
    password_hasher.hash = AsyncMock()
    view = AccountAdmin(Account, password_hasher)
    account = Account(login='hero', password_hash='initial')
    set_committed_value(account, 'password_hash', '$argon2id$stored-hash')
    account.password_hash = ''

    await view.before_edit(
        SimpleNamespace(),
        {'password_hash': ''},
        account,
    )

    assert account.password_hash == '$argon2id$stored-hash'
    password_hasher.hash.assert_not_awaited()

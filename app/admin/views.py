from html import escape
from typing import Any

from sqlalchemy import String, cast, inspect, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette_admin._types import RequestAction
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError
from starlette_admin.fields import PasswordField, RelationField

from app.admin.fields import ImageUploadField
from app.core.files.images import ImageService, InvalidImageError
from app.core.files.repository import FileStorageError
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
from app.modules.content.expressions import InvalidExpressionError, validate_expression
from app.modules.content.models import ActionDefinition, ActionEffect, EffectDefinition, EffectRule
from app.modules.locations.models import Location, LocationTransition
from app.modules.stats.models import StatDefinition


class SoftDeleteModelView(ModelView):
    exclude_fields_from_list = ['id', 'created_at', 'updated_at']
    exclude_fields_from_create = ['created_at', 'updated_at']
    exclude_fields_from_edit = ['created_at', 'updated_at']
    fields_default_sort = [('created_at', True)]

    def __init__(self, model: type[Any], **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self.fields.sort(
            key=lambda field: (
                field.name not in {'login', 'nickname', 'title', 'display_name', 'code', 'action_code', 'effect_code'},
                not isinstance(field, RelationField),
                field.name in {'id', 'created_at', 'updated_at', 'is_archived'},
            )
        )
        relationships = inspect(model).relationships
        readonly_columns = {
            column.key
            for relationship in relationships
            if relationship.viewonly
            for column in relationship.local_columns
        }
        for field in self.fields:
            if field.name in readonly_columns:
                field.exclude_from_list = True
            if isinstance(field, RelationField) and relationships[field.name].viewonly:
                field.exclude_from_create = True
                field.exclude_from_edit = True

    async def select2_result(self, obj: Any, request: Request) -> str:
        return f'<span>{escape(await self.repr(obj, request))}</span>'

    def _validate_order_by(self, request: Request, order_by: list[str]) -> str | None:
        # Relation selects sort by the primary key, even when it is hidden from list pages.
        if request.state.action is RequestAction.API and order_by == [f'{self.pk_attr} asc']:
            return None
        return super()._validate_order_by(request, order_by)

    def build_order_clauses(self, request: Request, order_list: list[str], stmt: Any) -> Any:
        return super().build_order_clauses(request, order_list or ['created_at desc'], stmt)

    async def delete(self, request: Request, pks: list[Any]) -> int:
        session = request.state.session
        if not isinstance(session, AsyncSession):
            raise TypeError('The administration panel requires AsyncSession')

        objects = await self.find_by_pks(request, pks)
        for obj in objects:
            await self.before_delete(request, obj)
            obj.is_archived = True
            session.add(obj)
        await session.commit()
        for obj in objects:
            await self.after_delete(request, obj)
        return len(objects)


class AccountAdmin(SoftDeleteModelView):
    fields = [
        'id',
        'created_at',
        'updated_at',
        'is_archived',
        'login',
        PasswordField(
            'password_hash',
            label='Password',
            exclude_from_list=True,
            exclude_from_detail=True,
            searchable=False,
            orderable=False,
            required=False,
        ),
        'character',
    ]
    exclude_fields_from_create = [
        *SoftDeleteModelView.exclude_fields_from_create,
        'character',
        'sessions',
    ]
    exclude_fields_from_edit = [
        *SoftDeleteModelView.exclude_fields_from_edit,
        'character',
        'sessions',
    ]
    searchable_fields = ['login']
    sortable_fields = ['id', 'login', 'created_at', 'is_archived']
    export_fields = ['id', 'login', 'created_at', 'updated_at', 'is_archived']

    def __init__(self, model: type[Any], password_hasher: PasswordHasher, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self.password_hasher = password_hasher

    async def serialize(
        self,
        obj: Any,
        request: Request,
        action: RequestAction,
        include_relationships: bool = True,
        include_select2: bool = False,
    ) -> dict[str, Any]:
        result = await super().serialize(
            obj,
            request,
            action,
            include_relationships,
            include_select2,
        )
        result.pop('password_hash', None)
        return result

    async def before_create(self, request: Request, data: dict[str, Any], obj: Account) -> None:
        password = data.get('password_hash')
        if not isinstance(password, str) or not password:
            raise FormValidationError({'password_hash': 'Password is required'})
        obj.password_hash = await self.password_hasher.hash(password)
        await super().before_create(request, data, obj)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Account) -> None:
        password = data.get('password_hash')
        if isinstance(password, str) and password:
            obj.password_hash = await self.password_hasher.hash(password)
        else:
            history = inspect(obj).attrs.password_hash.history
            if history.deleted:
                obj.password_hash = history.deleted[0]
        await super().before_edit(request, data, obj)


class SessionAdmin(SoftDeleteModelView):
    fields = [
        'id',
        'created_at',
        'updated_at',
        'is_archived',
        'account',
        'active_character',
        PasswordField(
            'refresh_token_hash',
            label='Refresh token hash',
            exclude_from_list=True,
            exclude_from_detail=True,
            searchable=False,
            orderable=False,
            required=True,
        ),
        'ip_address',
        'user_agent',
        'expires_at',
    ]
    searchable_fields = ['id', 'account', 'active_character', 'ip_address']
    sortable_fields = [
        'id',
        'account_id',
        'active_character_id',
        'expires_at',
        'created_at',
        'is_archived',
    ]


class CharacterAdmin(SoftDeleteModelView):
    searchable_fields = ['nickname']
    sortable_fields = ['id', 'nickname', 'class_id', 'created_at', 'is_archived']


class FightAdmin(SoftDeleteModelView):
    searchable_fields = ['id', 'status']
    sortable_fields = ['id', 'status', 'version', 'created_at', 'is_archived']

    def get_search_query(self, request: Request, term: str) -> Any:
        del request
        pattern = f'%{term}%'
        return or_(
            cast(Fight.id, String).ilike(pattern),
            cast(Fight.status, String).ilike(pattern),
        )


class FightParticipantsAdmin(SoftDeleteModelView):
    searchable_fields = ['id', 'fight_id', 'source_id', 'display_name']
    sortable_fields = ['id', 'side', 'created_at', 'is_archived']

    def get_search_query(self, request: Request, term: str) -> Any:
        del request
        pattern = f'%{term}%'
        return or_(
            cast(FightParticipants.id, String).ilike(pattern),
            cast(FightParticipants.fight_id, String).ilike(pattern),
            FightParticipants.display_name.ilike(pattern),
        )


class ContentModelAdmin(SoftDeleteModelView):
    sortable_fields = ['id', 'created_at', 'is_archived']


class ImageContentAdmin(ContentModelAdmin):
    def __init__(self, model: type[Any], images: ImageService | None = None, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self.images = images
        position = next(index for index, field in enumerate(self.fields) if field.name == 'image_url')
        self.fields.insert(
            position,
            ImageUploadField(
                'image_upload',
                label='Image',
                accept='image/png,image/jpeg,image/webp,image/gif',
                help_text='Upload replaces Image URL. Delete clears the link; the stored file is retained.',
                searchable=False,
                orderable=False,
            ),
        )

    async def _populate_obj(
        self,
        request: Request,
        obj: Any,
        data: dict[str, Any],
        is_edit: bool = False,
    ) -> Any:
        upload, remove = data.get('image_upload', (None, False))
        # The upload field is virtual: only image_url is persisted in the model.
        obj = await super()._populate_obj(request, obj, {**data, 'image_upload': (None, False)}, is_edit)
        if remove:
            obj.image_url = None
        elif upload is not None:
            if self.images is None:
                raise FormValidationError({'image_upload': 'Image uploads are disabled. Configure S3_ENABLED.'})
            try:
                obj.image_url = await self.images.upload(upload)
            except (InvalidImageError, FileStorageError) as error:
                raise FormValidationError({'image_upload': str(error)}) from error
        return obj


class EffectRuleAdmin(ContentModelAdmin):
    async def before_create(self, request: Request, data: dict[str, Any], obj: EffectRule) -> None:
        await self._validate(request, obj)
        await super().before_create(request, data, obj)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: EffectRule) -> None:
        await self._validate(request, obj)
        await super().before_edit(request, data, obj)

    @staticmethod
    async def _validate(request: Request, obj: EffectRule) -> None:
        session = request.state.session
        available_stat_codes = None
        if isinstance(session, AsyncSession):
            result = await session.execute(
                select(StatDefinition.code).where(
                    StatDefinition.is_archived.is_(False),
                ),
            )
            available_stat_codes = set(result.scalars())
        try:
            validate_expression(
                obj.evaluator_type,
                obj.expression,
                available_stat_codes=available_stat_codes,
                allow_random=obj.kind.value != 'stat_modifier',
            )
        except InvalidExpressionError as error:
            raise FormValidationError({'expression': str(error)}) from error


def create_admin_views(password_hasher: PasswordHasher, images: ImageService | None = None) -> tuple[ModelView, ...]:
    return (
        AccountAdmin(Account, password_hasher, icon='fa-solid fa-user-lock', label='Accounts'),
        SessionAdmin(Session, icon='fa-solid fa-key', label='Sessions'),
        ImageContentAdmin(Location, images, icon='fa-solid fa-map', label='Locations'),
        ContentModelAdmin(LocationTransition, icon='fa-solid fa-route', label='Location transitions'),
        CharacterAdmin(Character, icon='fa-solid fa-user', label='Characters'),
        FightAdmin(Fight, icon='fa-solid fa-shield-halved', label='Fights'),
        FightParticipantsAdmin(
            FightParticipants,
            icon='fa-solid fa-users',
            label='Fight participants',
        ),
        ContentModelAdmin(BotTemplate, icon='fa-solid fa-paw', label='Bot templates'),
        ContentModelAdmin(BotTemplateStat, icon='fa-solid fa-chart-line', label='Bot stats'),
        ContentModelAdmin(BotTemplateAction, icon='fa-solid fa-bolt', label='Bot actions'),
        ContentModelAdmin(CharacterClass, icon='fa-solid fa-hat-wizard', label='Character classes'),
        ContentModelAdmin(StatDefinition, icon='fa-solid fa-chart-simple', label='Stat definitions'),
        ContentModelAdmin(ClassStat, icon='fa-solid fa-sliders', label='Class stats'),
        ContentModelAdmin(CharacterStat, icon='fa-solid fa-chart-line', label='Character stats'),
        ImageContentAdmin(ActionDefinition, images, icon='fa-solid fa-bolt', label='Action definitions'),
        ImageContentAdmin(EffectDefinition, images, icon='fa-solid fa-wand-sparkles', label='Effect definitions'),
        EffectRuleAdmin(EffectRule, icon='fa-solid fa-code', label='Effect rules'),
        ContentModelAdmin(ActionEffect, icon='fa-solid fa-link', label='Action effects'),
        ContentModelAdmin(ClassAction, icon='fa-solid fa-link', label='Class actions'),
        ContentModelAdmin(CharacterAction, icon='fa-solid fa-link', label='Character actions'),
        ContentModelAdmin(FightParticipantStat, icon='fa-solid fa-chart-column', label='Fight stats'),
        ContentModelAdmin(FightActiveEffect, icon='fa-solid fa-fire', label='Fight effects'),
        ContentModelAdmin(FightAction, icon='fa-solid fa-hand-fist', label='Fight actions'),
        ContentModelAdmin(FightEvent, icon='fa-solid fa-list', label='Fight events'),
    )

from html import escape
from typing import Any

from sqlalchemy import String, cast, or_
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette_admin._types import RequestAction
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError
from starlette_admin.fields import PasswordField

from app.models import (
    Account,
    Actions,
    Character,
    Characteristics,
    CharacteristicsActions,
    Fight,
    FightActions,
    FightParticipants,
    Mob,
)


class SoftDeleteModelView(ModelView):
    exclude_fields_from_create = ['created_at', 'updated_at']
    exclude_fields_from_edit = ['created_at', 'updated_at']
    fields_default_sort = [('created_at', True)]

    async def select2_result(self, obj: Any, request: Request) -> str:
        return f'<span>{escape(await self.repr(obj, request))}</span>'

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
            'password',
            exclude_from_list=True,
            exclude_from_detail=True,
            searchable=False,
            orderable=False,
            required=True,
        ),
        'character',
    ]
    exclude_fields_from_create = [*SoftDeleteModelView.exclude_fields_from_create, 'character']
    exclude_fields_from_edit = [*SoftDeleteModelView.exclude_fields_from_edit, 'character']
    searchable_fields = ['login']
    sortable_fields = ['id', 'login', 'created_at', 'is_archived']
    export_fields = ['id', 'login', 'created_at', 'updated_at', 'is_archived']

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
        result.pop('password', None)
        return result


class CharacterAdmin(SoftDeleteModelView):
    exclude_fields_from_list = ['fight_participations']
    exclude_fields_from_create = [
        *SoftDeleteModelView.exclude_fields_from_create,
        'fight_participations',
    ]
    exclude_fields_from_edit = [
        *SoftDeleteModelView.exclude_fields_from_edit,
        'fight_participations',
    ]
    searchable_fields = ['nickname']
    sortable_fields = ['id', 'nickname', 'character_class', 'created_at', 'is_archived']


class MobAdmin(SoftDeleteModelView):
    exclude_fields_from_list = ['fight_participations']
    exclude_fields_from_create = [
        *SoftDeleteModelView.exclude_fields_from_create,
        'fight_participations',
    ]
    exclude_fields_from_edit = [
        *SoftDeleteModelView.exclude_fields_from_edit,
        'fight_participations',
    ]
    searchable_fields = ['name']
    sortable_fields = ['id', 'name', 'created_at', 'is_archived']


class ActionsAdmin(SoftDeleteModelView):
    exclude_fields_from_list = ['characteristic_links', 'fight_actions']
    exclude_fields_from_create = [
        *SoftDeleteModelView.exclude_fields_from_create,
        'characteristic_links',
        'fight_actions',
    ]
    exclude_fields_from_edit = [
        *SoftDeleteModelView.exclude_fields_from_edit,
        'characteristic_links',
        'fight_actions',
    ]
    searchable_fields = ['title', 'description']
    sortable_fields = ['id', 'title', 'type', 'is_active', 'created_at', 'is_archived']


class CharacteristicsAdmin(SoftDeleteModelView):
    exclude_fields_from_list = ['action_links']
    exclude_fields_from_create = [
        *SoftDeleteModelView.exclude_fields_from_create,
        'action_links',
    ]
    exclude_fields_from_edit = [
        *SoftDeleteModelView.exclude_fields_from_edit,
        'action_links',
    ]
    searchable_fields = ['title', 'description']
    sortable_fields = ['id', 'title', 'value', 'created_at', 'is_archived']


class CharacteristicsActionsAdmin(SoftDeleteModelView):
    searchable_fields = ['characteristic', 'action']
    sortable_fields = ['id', 'affect', 'created_at', 'is_archived']


class FightAdmin(SoftDeleteModelView):
    exclude_fields_from_list = ['participants', 'actions']
    exclude_fields_from_create = [
        *SoftDeleteModelView.exclude_fields_from_create,
        'participants',
        'actions',
    ]
    exclude_fields_from_edit = [
        *SoftDeleteModelView.exclude_fields_from_edit,
        'participants',
        'actions',
    ]
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
    exclude_fields_from_list = ['initiated_actions', 'targeted_actions']
    exclude_fields_from_create = [
        *SoftDeleteModelView.exclude_fields_from_create,
        'initiated_actions',
        'targeted_actions',
    ]
    exclude_fields_from_edit = [
        *SoftDeleteModelView.exclude_fields_from_edit,
        'initiated_actions',
        'targeted_actions',
    ]
    searchable_fields = ['id', 'fight', 'character', 'mob']
    sortable_fields = ['id', 'side', 'created_at', 'is_archived']

    def get_search_query(self, request: Request, term: str) -> Any:
        del request
        pattern = f'%{term}%'
        return or_(
            cast(FightParticipants.id, String).ilike(pattern),
            cast(FightParticipants.fight_id, String).ilike(pattern),
            FightParticipants.character.has(Character.nickname.ilike(pattern)),
            FightParticipants.mob.has(Mob.name.ilike(pattern)),
        )

    async def select2_result(self, obj: FightParticipants, request: Request) -> str:
        del request
        actor = obj.character.nickname if obj.character is not None else obj.mob.name
        label = escape(f'{actor} — {obj.side.value} — fight {obj.fight_id}')
        return f'<span>{label}</span>'

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        if (data.get('character') is None) == (data.get('mob') is None):
            raise FormValidationError(
                {
                    'character': 'Select exactly one actor: character or mob',
                    'mob': 'Select exactly one actor: character or mob',
                },
            )
        await super().validate(request, data)


class FightActionsAdmin(SoftDeleteModelView):
    searchable_fields = ['id', 'fight', 'action', 'initiator_participant']
    sortable_fields = ['id', 'created_at', 'is_archived']

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        fight = data.get('fight')
        initiator = data.get('initiator_participant')
        target = data.get('target_participant')
        errors: dict[str, str] = {}
        if fight is not None and initiator is not None and initiator.fight_id != fight.id:
            errors['initiator_participant'] = 'Initiator must belong to the selected fight'
        if fight is not None and target is not None and target.fight_id != fight.id:
            errors['target_participant'] = 'Target must belong to the selected fight'
        if errors:
            raise FormValidationError(errors)
        await super().validate(request, data)


def create_admin_views() -> tuple[ModelView, ...]:
    return (
        AccountAdmin(Account, icon='fa-solid fa-user-lock', label='Accounts'),
        CharacterAdmin(Character, icon='fa-solid fa-user', label='Characters'),
        MobAdmin(Mob, icon='fa-solid fa-dragon', label='Mobs'),
        ActionsAdmin(Actions, icon='fa-solid fa-wand-magic-sparkles', label='Actions'),
        CharacteristicsAdmin(
            Characteristics,
            icon='fa-solid fa-chart-simple',
            label='Characteristics',
        ),
        CharacteristicsActionsAdmin(
            CharacteristicsActions,
            icon='fa-solid fa-link',
            label='Characteristic actions',
        ),
        FightAdmin(Fight, icon='fa-solid fa-shield-halved', label='Fights'),
        FightParticipantsAdmin(
            FightParticipants,
            icon='fa-solid fa-users',
            label='Fight participants',
        ),
        FightActionsAdmin(
            FightActions,
            icon='fa-solid fa-bolt',
            label='Fight actions',
        ),
    )

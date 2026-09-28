from uuid import UUID

from sqlalchemy import select

from app.core.db.entity_repository import EntityRepository
from app.modules.content.models import ActionDefinition, ActionEffect, EffectDefinition, EffectRule


class ActionDefinitionRepository(EntityRepository[ActionDefinition]):
    entity = ActionDefinition


class EffectDefinitionRepository(EntityRepository[EffectDefinition]):
    entity = EffectDefinition


class EffectRuleRepository(EntityRepository[EffectRule]):
    entity = EffectRule

    async def list_for_effect(self, effect_id: UUID) -> list[EffectRule]:
        rows = await self.fetch(
            select(self.table)
            .where(self.table.c.effect_definition_id == effect_id, self.table.c.is_archived.is_(False))
            .order_by(self.table.c.priority, self.table.c.created_at),
        )
        return [self._to_entity(row) for row in rows]


class ActionEffectRepository(EntityRepository[ActionEffect]):
    entity = ActionEffect

    async def list_for_action(self, action_id: UUID) -> list[ActionEffect]:
        rows = await self.fetch(
            select(self.table)
            .where(self.table.c.action_definition_id == action_id, self.table.c.is_archived.is_(False))
            .order_by(self.table.c.order, self.table.c.created_at),
        )
        return [self._to_entity(row) for row in rows]

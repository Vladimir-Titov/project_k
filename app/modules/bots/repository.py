from uuid import UUID

from sqlalchemy import select

from app.core.db.entity_repository import EntityRepository
from app.modules.bots.models import BotTemplate, BotTemplateAction, BotTemplateStat


class BotTemplateRepository(EntityRepository[BotTemplate]):
    entity = BotTemplate

    async def list_active(self) -> list[BotTemplate]:
        rows = await self.fetch(
            select(self.table)
            .where(self.table.c.is_active.is_(True), self.table.c.is_archived.is_(False))
            .order_by(self.table.c.title),
        )
        return [self._to_entity(row) for row in rows]


class BotTemplateStatRepository(EntityRepository[BotTemplateStat]):
    entity = BotTemplateStat

    async def list_for_template(self, template_id: UUID) -> list[BotTemplateStat]:
        rows = await self.fetch(
            select(self.table).where(
                self.table.c.bot_template_id == template_id,
                self.table.c.is_archived.is_(False),
            ),
        )
        return [self._to_entity(row) for row in rows]


class BotTemplateActionRepository(EntityRepository[BotTemplateAction]):
    entity = BotTemplateAction

    async def list_for_template(self, template_id: UUID) -> list[BotTemplateAction]:
        rows = await self.fetch(
            select(self.table)
            .where(self.table.c.bot_template_id == template_id, self.table.c.is_archived.is_(False))
            .order_by(self.table.c.priority, self.table.c.created_at),
        )
        return [self._to_entity(row) for row in rows]

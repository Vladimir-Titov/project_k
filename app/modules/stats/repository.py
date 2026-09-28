from sqlalchemy import select

from app.core.db.entity_repository import EntityRepository
from app.modules.stats.models import StatDefinition


class StatDefinitionRepository(EntityRepository[StatDefinition]):
    entity = StatDefinition

    async def get_by_code(self, code: str) -> StatDefinition | None:
        row = await self.fetchrow(select(self.table).where(self.table.c.code == code))
        return self._to_entity(row) if row is not None else None

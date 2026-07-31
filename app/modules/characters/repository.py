from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

from app.core.db.entity_repository import EntityRepository
from app.modules.characters.models import Character


class CharacterRepository(EntityRepository[Character]):
    entity = Character

    async def create_if_available(
        self,
        *,
        account_id: UUID,
        nickname: str,
    ) -> Character | None:
        payload = self.payload_model.model_validate(
            {
                'account_id': account_id,
                'nickname': nickname,
            },
        )
        query = (
            postgresql_insert(self.table)
            .values(self._insert_values(payload))
            .on_conflict_do_nothing()
            .returning(self.table)
        )
        row = await self.fetchrow(query)
        return self._to_entity(row) if row is not None else None

    async def get_active_by_account_id(
        self,
        account_id: UUID,
    ) -> Character | None:
        row = await self.fetchrow(
            select(self.table).where(
                self.table.c.account_id == account_id,
                self.table.c.is_archived.is_(False),
            ),
        )
        return self._to_entity(row) if row is not None else None

    async def get_by_account_id(
        self,
        account_id: UUID,
    ) -> Character | None:
        row = await self.fetchrow(
            select(self.table).where(
                self.table.c.account_id == account_id,
            ),
        )
        return self._to_entity(row) if row is not None else None

    async def get_active_by_nickname(
        self,
        nickname: str,
    ) -> Character | None:
        row = await self.fetchrow(
            select(self.table).where(
                self.table.c.nickname == nickname,
                self.table.c.is_archived.is_(False),
            ),
        )
        return self._to_entity(row) if row is not None else None

    async def get_by_nickname(
        self,
        nickname: str,
    ) -> Character | None:
        row = await self.fetchrow(
            select(self.table).where(
                self.table.c.nickname == nickname,
            ),
        )
        return self._to_entity(row) if row is not None else None

    async def get_active_for_account(
        self,
        *,
        character_id: UUID,
        account_id: UUID,
    ) -> Character | None:
        row = await self.fetchrow(
            select(self.table).where(
                self.table.c.id == character_id,
                self.table.c.account_id == account_id,
                self.table.c.is_archived.is_(False),
            ),
        )
        return self._to_entity(row) if row is not None else None

    async def list_active_for_account(
        self,
        account_id: UUID,
    ) -> list[Character]:
        rows = await self.fetch(
            select(self.table)
            .where(
                self.table.c.account_id == account_id,
                self.table.c.is_archived.is_(False),
            )
            .order_by(self.table.c.created_at),
        )
        return [self._to_entity(row) for row in rows]

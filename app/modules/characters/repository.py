from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

from app.core.db.entity_repository import EntityRepository
from app.modules.characters.models import (
    Character,
    CharacterAction,
    CharacterClass,
    CharacterStat,
    ClassAction,
    ClassStat,
)


class CharacterClassRepository(EntityRepository[CharacterClass]):
    entity = CharacterClass

    async def get_playable_by_code(self, code: str) -> CharacterClass | None:
        row = await self.fetchrow(
            select(self.table).where(
                self.table.c.code == code,
                self.table.c.is_playable.is_(True),
                self.table.c.is_archived.is_(False),
            ),
        )
        return self._to_entity(row) if row is not None else None

    async def list_playable(self) -> list[CharacterClass]:
        rows = await self.fetch(
            select(self.table)
            .where(self.table.c.is_playable.is_(True), self.table.c.is_archived.is_(False))
            .order_by(self.table.c.created_at),
        )
        return [self._to_entity(row) for row in rows]


class ClassStatRepository(EntityRepository[ClassStat]):
    entity = ClassStat

    async def list_for_class(self, class_id: UUID) -> list[ClassStat]:
        rows = await self.fetch(
            select(self.table).where(self.table.c.class_id == class_id, self.table.c.is_archived.is_(False)),
        )
        return [self._to_entity(row) for row in rows]


class ClassActionRepository(EntityRepository[ClassAction]):
    entity = ClassAction

    async def list_for_class(self, class_id: UUID) -> list[ClassAction]:
        rows = await self.fetch(
            select(self.table).where(self.table.c.class_id == class_id, self.table.c.is_archived.is_(False)),
        )
        return [self._to_entity(row) for row in rows]


class CharacterStatRepository(EntityRepository[CharacterStat]):
    entity = CharacterStat

    async def list_for_character(self, character_id: UUID, *, for_update: bool = False) -> list[CharacterStat]:
        query = select(self.table).where(
            self.table.c.character_id == character_id,
            self.table.c.is_archived.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        return [self._to_entity(row) for row in await self.fetch(query)]

    async def set_value(self, stat_id: UUID, value: object) -> None:
        await self.execute(update(self.table).where(self.table.c.id == stat_id).values(value=value))


class CharacterActionRepository(EntityRepository[CharacterAction]):
    entity = CharacterAction

    async def list_for_character(self, character_id: UUID) -> list[CharacterAction]:
        rows = await self.fetch(
            select(self.table).where(
                self.table.c.character_id == character_id,
                self.table.c.is_archived.is_(False),
            ),
        )
        return [self._to_entity(row) for row in rows]


class CharacterRepository(EntityRepository[Character]):
    entity = Character

    async def get_for_update(self, character_id: UUID) -> Character | None:
        row = await self.fetchrow(select(self.table).where(self.table.c.id == character_id).with_for_update())
        return self._to_entity(row) if row is not None else None

    async def set_location(self, character_id: UUID, location_id: UUID, next_movement_at: datetime) -> None:
        await self.execute(
            update(self.table)
            .where(self.table.c.id == character_id)
            .values(
                location_id=location_id,
                next_movement_at=next_movement_at,
            )
        )

    async def create_if_available(
        self,
        *,
        account_id: UUID,
        nickname: str,
        class_id: UUID,
    ) -> Character | None:
        payload = self.payload_model.model_validate(
            {
                'account_id': account_id,
                'nickname': nickname,
                'class_id': class_id,
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

    async def list_active_except(self, character_id: UUID) -> list[Character]:
        rows = await self.fetch(
            select(self.table)
            .where(self.table.c.id != character_id, self.table.c.is_archived.is_(False))
            .order_by(self.table.c.nickname),
        )
        return [self._to_entity(row) for row in rows]

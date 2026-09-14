from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

from app.core.db.entity_repository import EntityRepository
from app.modules.battles.models import (
    Fight,
    FightAction,
    FightActiveEffect,
    FightEvent,
    FightParticipants,
    FightParticipantStat,
)


class FightRepository(EntityRepository[Fight]):
    entity = Fight

    async def get_for_update(self, fight_id: UUID) -> Fight | None:
        row = await self.fetchrow(select(self.table).where(self.table.c.id == fight_id).with_for_update())
        return self._to_entity(row) if row is not None else None

    async def update_state(self, fight_id: UUID, **values: Any) -> None:
        await self.execute(update(self.table).where(self.table.c.id == fight_id).values(**values))


class FightParticipantRepository(EntityRepository[FightParticipants]):
    entity = FightParticipants

    async def list_for_fight(self, fight_id: UUID, *, for_update: bool = False) -> list[FightParticipants]:
        query = (
            select(self.table)
            .where(self.table.c.fight_id == fight_id, self.table.c.is_archived.is_(False))
            .order_by(self.table.c.turn_order)
        )
        if for_update:
            query = query.with_for_update()
        return [self._to_entity(row) for row in await self.fetch(query)]

    async def get_for_character(
        self,
        *,
        fight_id: UUID,
        character_id: UUID,
        for_update: bool = False,
    ) -> FightParticipants | None:
        query = select(self.table).where(
            self.table.c.fight_id == fight_id,
            self.table.c.source_type == 'character',
            self.table.c.source_id == character_id,
            self.table.c.is_archived.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        row = await self.fetchrow(query)
        return self._to_entity(row) if row is not None else None

    async def get_in_fight(self, fight_id: UUID, participant_id: UUID) -> FightParticipants | None:
        row = await self.fetchrow(
            select(self.table).where(
                self.table.c.fight_id == fight_id,
                self.table.c.id == participant_id,
                self.table.c.is_archived.is_(False),
            ),
        )
        return self._to_entity(row) if row is not None else None

    async def get_active_for_source(self, source_type: str, source_id: UUID) -> FightParticipants | None:
        row = await self.fetchrow(
            select(self.table).where(
                self.table.c.source_type == source_type,
                self.table.c.source_id == source_id,
                self.table.c.is_active.is_(True),
                self.table.c.is_archived.is_(False),
            ),
        )
        return self._to_entity(row) if row is not None else None

    async def deactivate_for_fight(self, fight_id: UUID) -> None:
        await self.execute(update(self.table).where(self.table.c.fight_id == fight_id).values(is_active=False))


class FightParticipantStatRepository(EntityRepository[FightParticipantStat]):
    entity = FightParticipantStat

    async def list_for_participant(
        self,
        participant_id: UUID,
        *,
        for_update: bool = False,
    ) -> list[FightParticipantStat]:
        query = select(self.table).where(
            self.table.c.participant_id == participant_id,
            self.table.c.is_archived.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        return [self._to_entity(row) for row in await self.fetch(query)]

    async def set_current_value(self, stat_id: UUID, value: object) -> None:
        await self.execute(update(self.table).where(self.table.c.id == stat_id).values(current_value=value))


class FightActiveEffectRepository(EntityRepository[FightActiveEffect]):
    entity = FightActiveEffect

    async def list_for_fight(self, fight_id: UUID, *, for_update: bool = False) -> list[FightActiveEffect]:
        query = select(self.table).where(
            self.table.c.fight_id == fight_id,
            self.table.c.is_archived.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        return [self._to_entity(row) for row in await self.fetch(query)]

    async def get_for_target_code(self, target_participant_id: UUID, effect_code: str) -> FightActiveEffect | None:
        row = await self.fetchrow(
            select(self.table).where(
                self.table.c.target_participant_id == target_participant_id,
                self.table.c.effect_code == effect_code,
                self.table.c.is_archived.is_(False),
            ),
        )
        return self._to_entity(row) if row is not None else None

    async def refresh(self, effect_id: UUID, *, remaining_turns: int, applied_turn: int) -> None:
        await self.execute(
            update(self.table)
            .where(self.table.c.id == effect_id)
            .values(remaining_turns=remaining_turns, applied_turn=applied_turn),
        )

    async def set_remaining_turns(self, effect_id: UUID, remaining_turns: int) -> None:
        await self.execute(
            update(self.table).where(self.table.c.id == effect_id).values(remaining_turns=remaining_turns),
        )

    async def delete(self, effect_id: UUID) -> None:
        await self.execute(delete(self.table).where(self.table.c.id == effect_id))


class FightActionRepository(EntityRepository[FightAction]):
    entity = FightAction

    async def create_or_get(
        self,
        *,
        fight_id: UUID,
        initiator_participant_id: UUID,
        target_participant_id: UUID | None,
        idempotency_key: UUID,
        action_code: str,
        turn_number: int,
    ) -> tuple[FightAction, bool]:
        payload = self.payload_model.model_validate(
            {
                'fight_id': fight_id,
                'initiator_participant_id': initiator_participant_id,
                'target_participant_id': target_participant_id,
                'idempotency_key': idempotency_key,
                'action_code': action_code,
                'turn_number': turn_number,
            },
        )
        row = await self.fetchrow(
            postgresql_insert(self.table)
            .values(self._insert_values(payload))
            .on_conflict_do_nothing(constraint='uq_fight_action_idempotency')
            .returning(self.table),
        )
        if row is not None:
            return self._to_entity(row), True
        existing = await self.fetchrow(
            select(self.table).where(
                self.table.c.fight_id == fight_id,
                self.table.c.initiator_participant_id == initiator_participant_id,
                self.table.c.idempotency_key == idempotency_key,
            ),
        )
        if existing is None:
            raise RuntimeError('Idempotent fight action was not found after conflict')
        return self._to_entity(existing), False

    async def get_idempotent(
        self,
        *,
        fight_id: UUID,
        initiator_participant_id: UUID,
        idempotency_key: UUID,
    ) -> FightAction | None:
        row = await self.fetchrow(
            select(self.table).where(
                self.table.c.fight_id == fight_id,
                self.table.c.initiator_participant_id == initiator_participant_id,
                self.table.c.idempotency_key == idempotency_key,
            ),
        )
        return self._to_entity(row) if row is not None else None

    async def save_result(self, action_id: UUID, result: dict[str, Any]) -> None:
        await self.execute(update(self.table).where(self.table.c.id == action_id).values(result=result))


class FightEventRepository(EntityRepository[FightEvent]):
    entity = FightEvent

    async def list_after(self, fight_id: UUID, sequence_number: int) -> list[FightEvent]:
        rows = await self.fetch(
            select(self.table)
            .where(
                self.table.c.fight_id == fight_id,
                self.table.c.sequence_number > sequence_number,
                self.table.c.is_archived.is_(False),
            )
            .order_by(self.table.c.sequence_number),
        )
        return [self._to_entity(row) for row in rows]

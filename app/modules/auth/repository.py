from uuid import UUID

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

from app.core.db.entity_repository import EntityRepository
from app.modules.auth.models import Account, Session


class AccountRepository(EntityRepository[Account]):
    entity = Account

    async def create_if_login_available(
        self,
        *,
        login: str,
        password_hash: str,
    ) -> Account | None:
        payload = self.payload_model.model_validate(
            {
                'login': login,
                'password_hash': password_hash,
            },
        )
        query = (
            postgresql_insert(self.table)
            .values(self._insert_values(payload))
            .on_conflict_do_nothing(index_elements=[self.table.c.login])
            .returning(self.table)
        )
        row = await self.fetchrow(query)
        return self._to_entity(row) if row is not None else None

    async def get_by_login(self, login: str) -> Account | None:
        row = await self.fetchrow(
            select(self.table).where(self.table.c.login == login),
        )
        return self._to_entity(row) if row is not None else None

    async def get_active_by_login(self, login: str) -> Account | None:
        row = await self.fetchrow(
            select(self.table).where(
                self.table.c.login == login,
                self.table.c.is_archived.is_(False),
            ),
        )
        return self._to_entity(row) if row is not None else None


class SessionRepository(EntityRepository[Session]):
    entity = Session

    async def create_session(self, session: Session) -> Session:
        values = {
            column.name: getattr(session, column.name)
            for column in self.table.columns
        }
        query = insert(self.table).values(values).returning(self.table)
        row = await self.fetchrow(query)
        if row is None:
            raise RuntimeError('INSERT into sessions returned no row')
        return self._to_entity(row)

    async def get_active(
        self,
        *,
        session_id: UUID,
        account_id: UUID,
        for_update: bool = False,
    ) -> Session | None:
        session_table = Session.__table__
        account_table = Account.__table__
        query = (
            select(session_table)
            .join(
                account_table,
                account_table.c.id == session_table.c.account_id,
            )
            .where(
                session_table.c.id == session_id,
                session_table.c.account_id == account_id,
                session_table.c.is_archived.is_(False),
                session_table.c.expires_at > func.now(),
                account_table.c.is_archived.is_(False),
            )
        )
        if for_update:
            query = query.with_for_update(of=session_table)
        row = await self.fetchrow(query)
        return self._to_entity(row) if row is not None else None

    async def get_for_refresh_for_update(
        self,
        session_id: UUID,
    ) -> Session | None:
        session_table = Session.__table__
        account_table = Account.__table__
        query = (
            select(session_table)
            .join(
                account_table,
                account_table.c.id == session_table.c.account_id,
            )
            .where(
                session_table.c.id == session_id,
                session_table.c.is_archived.is_(False),
                account_table.c.is_archived.is_(False),
            )
            .with_for_update(of=session_table)
        )
        row = await self.fetchrow(query)
        return self._to_entity(row) if row is not None else None

    async def set_active_character(
        self,
        session_id: UUID,
        character_id: UUID,
    ) -> None:
        await self.execute(
            update(self.table)
            .where(self.table.c.id == session_id)
            .values(active_character_id=character_id),
        )

    async def replace_refresh_token_hash(
        self,
        session_id: UUID,
        refresh_token_hash: str,
    ) -> None:
        await self.execute(
            update(self.table)
            .where(self.table.c.id == session_id)
            .values(refresh_token_hash=refresh_token_hash),
        )

    async def delete_by_id(self, session_id: UUID) -> None:
        await self.execute(
            delete(self.table).where(self.table.c.id == session_id),
        )

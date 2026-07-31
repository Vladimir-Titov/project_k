from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest

from app.core.db.query import compile_query
from app.modules.auth.models import Account, Session
from app.modules.auth.repository import AccountRepository, SessionRepository


def account_row() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        'id': uuid7(),
        'created_at': now,
        'updated_at': now,
        'is_archived': False,
        'login': 'hero',
        'password_hash': '$argon2id$hash',
    }


@pytest.mark.asyncio
async def test_account_repository_loads_active_account() -> None:
    repository = AccountRepository(Mock())
    row = account_row()
    repository.fetchrow = AsyncMock(return_value=row)

    account = await repository.get_active_by_login('hero')

    assert account is not None
    assert account.login == 'hero'
    query = repository.fetchrow.await_args.args[0]
    sql, parameters = compile_query(query)
    assert 'FROM auth.users' in sql
    assert 'JOIN frontiers.characters' not in sql
    assert 'auth.users.login = $1::VARCHAR' in sql
    assert 'auth.users.is_archived IS false' in sql
    assert parameters == ('hero',)


@pytest.mark.asyncio
async def test_account_repository_checks_login_without_archived_filter() -> None:
    repository = AccountRepository(Mock())
    row = account_row()
    row['is_archived'] = True
    repository.fetchrow = AsyncMock(return_value=row)

    account = await repository.get_by_login('hero')

    assert account is not None
    assert account.is_archived
    query = repository.fetchrow.await_args.args[0]
    sql, parameters = compile_query(query)
    assert 'auth.users.login = $1::VARCHAR' in sql
    assert 'is_archived' not in sql.split('WHERE', maxsplit=1)[1]
    assert parameters == ('hero',)


@pytest.mark.asyncio
async def test_account_repository_uses_atomic_login_conflict_handling() -> None:
    repository = AccountRepository(Mock())
    repository.fetchrow = AsyncMock(return_value=None)

    account = await repository.create_if_login_available(
        login='hero',
        password_hash='$argon2id$hash',
    )

    assert account is None
    query = repository.fetchrow.await_args.args[0]
    sql, parameters = compile_query(query)
    assert sql.startswith('INSERT INTO auth.users')
    assert 'ON CONFLICT (login) DO NOTHING' in sql
    assert 'hero' in parameters
    assert '$argon2id$hash' in parameters


@pytest.mark.asyncio
async def test_session_repository_locks_session_during_refresh() -> None:
    repository = SessionRepository(Mock())
    now = datetime.now(UTC)
    row = {
        'id': uuid7(),
        'created_at': now,
        'updated_at': now,
        'is_archived': False,
        'account_id': uuid7(),
        'refresh_token_hash': 'a' * 64,
        'ip_address': None,
        'user_agent': None,
        'expires_at': now + timedelta(days=30),
        'active_character_id': uuid7(),
    }
    repository.fetchrow = AsyncMock(return_value=row)

    session = await repository.get_for_refresh_for_update(row['id'])

    assert isinstance(session, Session)
    assert session.active_character_id == row['active_character_id']
    query = repository.fetchrow.await_args.args[0]
    sql, _ = compile_query(query)
    assert 'FOR UPDATE OF sessions' in sql


@pytest.mark.asyncio
async def test_session_repository_physically_deletes_by_id() -> None:
    repository = SessionRepository(Mock())
    repository.execute = AsyncMock()
    session_id = uuid7()

    await repository.delete_by_id(session_id)

    query = repository.execute.await_args.args[0]
    sql, parameters = compile_query(query)
    assert sql.startswith('DELETE FROM auth.sessions')
    assert parameters == (session_id,)


def test_account_model_uses_password_hash_column() -> None:
    assert 'password_hash' in Account.__table__.c
    assert 'password' not in Account.__table__.c

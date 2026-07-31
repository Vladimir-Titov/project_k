from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from pydantic import ValidationError

from app.core.db.query import compile_query
from app.modules.battles.enums import FightSide, FightStatus
from app.modules.battles.models import Fight
from app.modules.battles.repository import FightRepository


def fight_row() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        'id': uuid7(),
        'created_at': now,
        'updated_at': now,
        'is_archived': False,
        'status': FightStatus.started.value,
        'version': 1,
        'winner_side': None,
        'title': 'Test fight',
    }


def test_dynamic_models_follow_entity_fields() -> None:
    assert set(FightRepository.payload_model.model_fields) == {'status', 'version', 'winner_side', 'title'}
    assert {
        'id',
        'status',
        'status_in',
        'version_ge',
        'created_at_ge',
        'winner_side_is',
    } <= set(FightRepository.filter_model.model_fields)


@pytest.mark.asyncio
async def test_create_validates_dynamic_kwargs_and_returns_entity() -> None:
    repository = FightRepository(Mock())
    row = fight_row()
    repository.fetchrow = AsyncMock(return_value=row)

    fight = await repository.create(status=FightStatus.started, title='Test fight')

    assert isinstance(fight, Fight)
    assert fight.id == row['id']
    query = repository.fetchrow.await_args.args[0]
    sql, parameters = compile_query(query)
    assert sql.startswith('INSERT INTO frontiers.fights')
    assert FightStatus.started in parameters


@pytest.mark.asyncio
async def test_create_rejects_unknown_or_system_fields() -> None:
    repository = FightRepository(Mock())

    with pytest.raises(ValidationError):
        await repository.create(id=uuid7())


@pytest.mark.asyncio
async def test_create_many_validates_payloads_and_returns_entities() -> None:
    repository = FightRepository(Mock())
    rows = [fight_row(), fight_row()]
    repository.fetch = AsyncMock(return_value=rows)

    fights = await repository.create_many(
        [
            {'status': FightStatus.started, 'title': 'First fight'},
            {'status': FightStatus.in_progress, 'version': 2, 'title': 'Second fight'},
        ],
    )

    assert [fight.id for fight in fights] == [row['id'] for row in rows]
    query = repository.fetch.await_args.args[0]
    sql, parameters = compile_query(query)
    assert sql.startswith('INSERT INTO frontiers.fights')
    assert sql.count('), (') == 1
    assert FightStatus.started in parameters
    assert FightStatus.in_progress in parameters
    assert 2 in parameters


@pytest.mark.asyncio
async def test_create_many_returns_empty_list_without_database_call() -> None:
    repository = FightRepository(Mock())
    repository.fetch = AsyncMock()

    fights = await repository.create_many([])

    assert fights == []
    repository.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_many_rejects_invalid_payload_before_database_call() -> None:
    repository = FightRepository(Mock())
    repository.fetch = AsyncMock()

    with pytest.raises(ValidationError):
        await repository.create_many(
            [
                {'status': FightStatus.started, 'title': 'Valid fight'},
                {'id': uuid7(), 'status': FightStatus.in_progress, 'title': 'Invalid fight'},
            ],
        )

    repository.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_builds_validated_filters_and_ordering() -> None:
    repository = FightRepository(Mock())
    row = fight_row()
    repository.fetch = AsyncMock(return_value=[row])
    created_ge = datetime(2026, 1, 1, tzinfo=UTC)

    fights = await repository.search(
        status_in=[FightStatus.started, FightStatus.in_progress],
        created_at_ge=created_ge,
        winner_side_is=None,
        order_by=['-created_at'],
        limit=25,
        offset=5,
    )

    assert fights[0].id == row['id']
    query = repository.fetch.await_args.args[0]
    sql, parameters = compile_query(query)
    assert 'fights.status IN' in sql
    assert 'fights.created_at >=' in sql
    assert 'fights.winner_side IS NULL' in sql
    assert 'ORDER BY frontiers.fights.created_at DESC' in sql
    assert 'LIMIT' in sql
    assert created_ge in parameters


@pytest.mark.asyncio
async def test_search_rejects_unknown_filter_before_database_call() -> None:
    repository = FightRepository(Mock())
    repository.fetch = AsyncMock()

    with pytest.raises(ValidationError):
        await repository.search(unknown='value')

    repository.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_maps_enum_values_to_entity() -> None:
    repository = FightRepository(Mock())
    row = fight_row()
    row['winner_side'] = FightSide.team_a.value
    repository.fetch = AsyncMock(return_value=[row])

    fights = await repository.search()

    assert fights[0].winner_side is FightSide.team_a

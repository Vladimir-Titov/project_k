from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from pydantic import ValidationError

from app.enums.fights import FightSide, FightStatus
from app.models.fights import Fight
from repositories.fights import FightRepository
from repositories.query import compile_query


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
    }


def test_dynamic_models_follow_entity_fields() -> None:
    assert set(FightRepository.payload_model.model_fields) == {'status', 'version', 'winner_side'}
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

    fight = await repository.create(status=FightStatus.started)

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

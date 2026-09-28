from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.characters.exceptions import CharacterBusyError
from app.modules.locations.exceptions import (
    InvalidMovementSpeedError,
    MovementCooldownError,
    TransitionUnavailableError,
)
from app.modules.locations.service import LocationService
from app.modules.locations.timing import calculate_cooldown


def build_service():
    source = SimpleNamespace(
        id=uuid4(), code='city', title='Город', description=None, image_url=None, is_archived=False
    )
    target = SimpleNamespace(
        id=uuid4(), code='forest', title='Лес', description=None, image_url=None, is_archived=False
    )
    hero = SimpleNamespace(id=uuid4(), location_id=source.id, next_movement_at=None, is_archived=False)
    road = SimpleNamespace(
        id=uuid4(),
        from_location_id=source.id,
        to_location_id=target.id,
        base_duration_seconds=30,
        is_enabled=True,
        is_archived=False,
    )
    stat_id = uuid4()

    async def set_location(character_id, location_id, deadline):
        assert character_id == hero.id
        hero.location_id, hero.next_movement_at = location_id, deadline

    repositories = SimpleNamespace(
        characters=SimpleNamespace(
            get_by_id=AsyncMock(return_value=hero),
            get_for_update=AsyncMock(return_value=hero),
            set_location=AsyncMock(side_effect=set_location),
        ),
        locations=SimpleNamespace(get_by_id=AsyncMock(side_effect={source.id: source, target.id: target}.get)),
        location_transitions=SimpleNamespace(get_by_id=AsyncMock(return_value=road), search=AsyncMock(return_value=[])),
        character_stats=SimpleNamespace(
            list_for_character=AsyncMock(return_value=[SimpleNamespace(stat_definition_id=stat_id, value=Decimal(100))])
        ),
        stat_definitions=SimpleNamespace(
            get_by_id=AsyncMock(return_value=SimpleNamespace(code='movement_speed', is_archived=False))
        ),
        fight_participants=SimpleNamespace(get_active_for_source=AsyncMock(return_value=None)),
    )
    return LocationService(repositories), hero, road, repositories


@pytest.mark.parametrize(('speed', 'expected'), [(100, 30), (150, 20), (200, 15), (110, 28), (10000, 1)])
def test_speed_formula(speed, expected):
    assert calculate_cooldown(30, Decimal(speed)) == expected


@pytest.mark.parametrize('speed', [Decimal(0), Decimal(-1), Decimal('NaN'), Decimal('Infinity')])
def test_invalid_speed(speed):
    with pytest.raises(InvalidMovementSpeedError):
        calculate_cooldown(30, speed)


@pytest.mark.asyncio
async def test_move_changes_location_immediately_and_persists_cooldown():
    service, hero, road, repos = build_service()
    before = datetime.now(UTC)
    response = await service.move(hero.id, road.id)
    assert response.location.id == road.to_location_id
    assert before + timedelta(seconds=30) <= response.next_movement_at <= datetime.now(UTC) + timedelta(seconds=30)
    repos.characters.get_for_update.assert_awaited_once_with(hero.id)
    with pytest.raises(MovementCooldownError):
        await service.move(hero.id, road.id)
    assert repos.characters.set_location.await_count == 1


@pytest.mark.asyncio
async def test_return_after_long_absence_does_not_restart_timer():
    service, hero, road, repos = build_service()
    deadline = datetime.now(UTC) - timedelta(hours=2)
    hero.next_movement_at = deadline
    response = await service.current(hero.id)
    assert response.next_movement_at == deadline
    repos.characters.set_location.assert_not_awaited()
    await service.move(hero.id, road.id)
    assert hero.location_id == road.to_location_id


@pytest.mark.asyncio
@pytest.mark.parametrize('reason', ['wrong_source', 'disabled', 'archived', 'missing', 'archived_destination'])
async def test_unavailable_road_rejected_without_changes(reason):
    service, hero, road, repos = build_service()
    if reason == 'wrong_source':
        road.from_location_id = uuid4()
    elif reason == 'disabled':
        road.is_enabled = False
    elif reason == 'archived':
        road.is_archived = True
    elif reason == 'missing':
        repos.location_transitions.get_by_id.return_value = None
    else:
        destination = await repos.locations.get_by_id(road.to_location_id)
        destination.is_archived = True
    with pytest.raises(TransitionUnavailableError):
        await service.move(hero.id, road.id)
    repos.characters.set_location.assert_not_awaited()


@pytest.mark.asyncio
async def test_active_fight_blocks_movement():
    service, hero, road, repos = build_service()
    repos.fight_participants.get_active_for_source.return_value = object()
    with pytest.raises(CharacterBusyError):
        await service.move(hero.id, road.id)
    repos.characters.set_location.assert_not_awaited()


@pytest.mark.asyncio
async def test_exits_are_filtered_by_current_location_and_speed_does_not_change_deadline():
    service, hero, road, repos = build_service()
    deadline = datetime.now(UTC) + timedelta(seconds=30)
    hero.next_movement_at = deadline
    repos.character_stats.list_for_character.return_value[0].value = Decimal(200)
    repos.location_transitions.search.return_value = [road]
    response = await service.current(hero.id)
    assert response.transitions[0].cooldown_seconds == 15
    assert response.next_movement_at == deadline
    assert repos.location_transitions.search.await_args.kwargs['from_location_id'] == hero.location_id

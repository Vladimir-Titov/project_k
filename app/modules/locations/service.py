from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from app.modules.characters.exceptions import CharacterBusyError, CharacterNotFoundError
from app.modules.locations.exceptions import (
    InvalidMovementSpeedError,
    LocationUnavailableError,
    MovementCooldownError,
    TransitionUnavailableError,
)
from app.modules.locations.schemas import LocationResponse, LocationStateResponse, TransitionResponse
from app.modules.locations.timing import calculate_cooldown

if TYPE_CHECKING:
    from app.container import Repositories


class LocationService:
    def __init__(self, repositories: Repositories) -> None:
        self.repositories = repositories

    async def _speed(self, character_id: UUID) -> Decimal:
        for stat in await self.repositories.character_stats.list_for_character(character_id):
            definition = await self.repositories.stat_definitions.get_by_id(stat.stat_definition_id)
            if definition is not None and not definition.is_archived and definition.code == 'movement_speed':
                return Decimal(stat.value)
        raise InvalidMovementSpeedError

    async def current(self, character_id: UUID) -> LocationStateResponse:
        character = await self.repositories.characters.get_by_id(character_id)
        if character is None or character.is_archived:
            raise CharacterNotFoundError
        location = await self.repositories.locations.get_by_id(character.location_id)
        if location is None or location.is_archived:
            raise LocationUnavailableError
        speed = await self._speed(character_id)
        transitions = []
        for road in await self.repositories.location_transitions.search(
            from_location_id=location.id,
            is_enabled=True,
            is_archived=False,
            order_by='created_at',
        ):
            destination = await self.repositories.locations.get_by_id(road.to_location_id)
            if destination is not None and not destination.is_archived:
                transitions.append(
                    TransitionResponse(
                        id=road.id,
                        destination=LocationResponse.model_validate(destination),
                        cooldown_seconds=calculate_cooldown(road.base_duration_seconds, speed),
                    )
                )
        return LocationStateResponse(
            location=LocationResponse.model_validate(location),
            next_movement_at=character.next_movement_at,
            server_time=datetime.now(UTC),
            transitions=transitions,
        )

    async def move(self, character_id: UUID, transition_id: UUID) -> LocationStateResponse:
        # The API unit of work keeps this lock until the whole request commits.
        character = await self.repositories.characters.get_for_update(character_id)
        if character is None or character.is_archived:
            raise CharacterNotFoundError
        now = datetime.now(UTC)
        if character.next_movement_at is not None and character.next_movement_at > now:
            raise MovementCooldownError
        if await self.repositories.fight_participants.get_active_for_source('character', character_id):
            raise CharacterBusyError
        road = await self.repositories.location_transitions.get_by_id(transition_id)
        if road is None or road.is_archived or not road.is_enabled or road.from_location_id != character.location_id:
            raise TransitionUnavailableError
        source = await self.repositories.locations.get_by_id(character.location_id)
        destination = await self.repositories.locations.get_by_id(road.to_location_id)
        if source is None or source.is_archived or destination is None or destination.is_archived:
            raise TransitionUnavailableError
        duration = calculate_cooldown(road.base_duration_seconds, await self._speed(character_id))
        await self.repositories.characters.set_location(
            character_id,
            destination.id,
            now + timedelta(seconds=duration),
        )
        return await self.current(character_id)

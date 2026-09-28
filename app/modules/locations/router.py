from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_active_character_context, get_unit_of_work
from app.container import Repositories
from app.modules.game_context.service import ActiveCharacterContext
from app.modules.locations.schemas import LocationStateResponse, MoveRequest
from app.modules.locations.service import LocationService

router = APIRouter(prefix='/api/v1/locations', tags=['locations'])


@router.get('/current', response_model=LocationStateResponse)
async def current_location(
    context: Annotated[ActiveCharacterContext, Depends(get_active_character_context)],
    repositories: Annotated[Repositories, Depends(get_unit_of_work)],
) -> LocationStateResponse:
    return await LocationService(repositories).current(context.character_id)


@router.post('/move', response_model=LocationStateResponse)
async def move(
    payload: MoveRequest,
    context: Annotated[ActiveCharacterContext, Depends(get_active_character_context)],
    repositories: Annotated[Repositories, Depends(get_unit_of_work)],
) -> LocationStateResponse:
    return await LocationService(repositories).move(context.character_id, payload.transition_id)

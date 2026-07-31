from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_active_character_context, get_fight_service
from app.modules.battles.schemas import CreateFightRequest, FightResponse
from app.modules.battles.service import FightService
from app.modules.game_context.service import ActiveCharacterContext

router = APIRouter(prefix='/api/v1/fights', tags=['fights'])


@router.post('', response_model=FightResponse, status_code=status.HTTP_201_CREATED)
async def create_fight(
    payload: CreateFightRequest,
    context: Annotated[ActiveCharacterContext, Depends(get_active_character_context)],
    fight_service: Annotated[FightService, Depends(get_fight_service)],
) -> FightResponse:
    fight = await fight_service.create_fight(
        attacker_id=context.character_id,
        target_id=payload.target_id,
    )
    return FightResponse.model_validate(fight)

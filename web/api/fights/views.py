from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.services import FightService, UserTokenPayload
from web.api.dependencies import get_current_user_token_payload, get_fight_service
from web.api.fights.schema import CreateFightRequest, FightResponse

router = APIRouter(prefix='/api/v1/fights', tags=['fights'])


@router.post('', response_model=FightResponse, status_code=status.HTTP_201_CREATED)
async def create_fight(
    payload: CreateFightRequest,
    token_payload: Annotated[UserTokenPayload, Depends(get_current_user_token_payload)],
    fight_service: Annotated[FightService, Depends(get_fight_service)],
) -> FightResponse:
    fight = await fight_service.create_fight(
        attacker_id=token_payload.character_id,
        target_id=payload.target_id,
    )
    return FightResponse.model_validate(fight)

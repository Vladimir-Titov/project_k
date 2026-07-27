from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.services import Services, UserTokenPayload
from web.api.dependencies import get_current_user_token_payload, get_services
from web.api.fights.schema import CreateFightRequest, FightResponse

router = APIRouter(prefix='/api/v1/fights', tags=['fights'])


@router.post('', response_model=FightResponse, status_code=status.HTTP_201_CREATED)
async def create_fight(
    payload: CreateFightRequest,
    token_payload: Annotated[UserTokenPayload, Depends(get_current_user_token_payload)],
    services: Annotated[Services, Depends(get_services)],
) -> FightResponse:
    fight = await services.create_fight(
        attacker_id=token_payload.character_id,
        target_id=payload.target_id,
    )
    return FightResponse.model_validate(fight)

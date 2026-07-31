from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_current_account_token_payload,
    get_fight_service,
)
from app.modules.auth.service import AccountTokenPayload
from app.modules.battles.schemas import CreateFightRequest, FightResponse
from app.modules.battles.service import FightService
from app.modules.characters.exceptions import CharacterRequiredError, InvalidGameSessionError

router = APIRouter(prefix='/api/v1/fights', tags=['fights'])


@router.post('', response_model=FightResponse, status_code=status.HTTP_201_CREATED)
async def create_fight(
    payload: CreateFightRequest,
    token_payload: Annotated[
        AccountTokenPayload,
        Depends(get_current_account_token_payload),
    ],
    fight_service: Annotated[FightService, Depends(get_fight_service)],
) -> FightResponse:
    try:
        fight = await fight_service.create_fight(
            account_id=token_payload.account_id,
            session_id=token_payload.session_id,
            target_id=payload.target_id,
        )
    except InvalidGameSessionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='invalid_or_expired_session',
        )
    except CharacterRequiredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='character_required',
        )
    return FightResponse.model_validate(fight)

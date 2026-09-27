from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_active_character_context, get_fight_service
from app.modules.battles.schemas import (
    BotTargetResponse,
    CreateBotFightRequest,
    CreateFightRequest,
    FightActionResponse,
    FightStateResponse,
    FightTargetResponse,
    PerformFightActionRequest,
)
from app.modules.battles.service import FightService
from app.modules.game_context.service import ActiveCharacterContext

router = APIRouter(prefix='/api/v1/fights', tags=['fights'])


@router.get('/targets', response_model=list[FightTargetResponse])
async def list_fight_targets(
    context: Annotated[ActiveCharacterContext, Depends(get_active_character_context)],
    fight_service: Annotated[FightService, Depends(get_fight_service)],
) -> list[FightTargetResponse]:
    return await fight_service.list_targets(context.character_id)


@router.post('', response_model=FightStateResponse, status_code=status.HTTP_201_CREATED)
async def create_fight(
    payload: CreateFightRequest,
    context: Annotated[ActiveCharacterContext, Depends(get_active_character_context)],
    fight_service: Annotated[FightService, Depends(get_fight_service)],
) -> FightStateResponse:
    fight = await fight_service.create_fight(attacker_id=context.character_id, target_id=payload.target_id)
    return await fight_service.get_state(fight_id=fight.id, character_id=context.character_id)


@router.get('/bot-targets', response_model=list[BotTargetResponse])
async def list_bot_targets(
    context: Annotated[ActiveCharacterContext, Depends(get_active_character_context)],
    fight_service: Annotated[FightService, Depends(get_fight_service)],
) -> list[BotTargetResponse]:
    return await fight_service.list_bot_targets(context.character_id)


@router.post('/bots', response_model=FightStateResponse, status_code=status.HTTP_201_CREATED)
async def create_bot_fight(
    payload: CreateBotFightRequest,
    context: Annotated[ActiveCharacterContext, Depends(get_active_character_context)],
    fight_service: Annotated[FightService, Depends(get_fight_service)],
) -> FightStateResponse:
    fight = await fight_service.create_bot_fight(
        attacker_id=context.character_id,
        bot_template_id=payload.bot_template_id,
    )
    return await fight_service.get_state(fight_id=fight.id, character_id=context.character_id)


@router.get('/active', response_model=FightStateResponse)
async def get_active_fight(
    context: Annotated[ActiveCharacterContext, Depends(get_active_character_context)],
    fight_service: Annotated[FightService, Depends(get_fight_service)],
    events_after: Annotated[int, Query(ge=0)] = 0,
) -> FightStateResponse:
    return await fight_service.get_active_state(character_id=context.character_id, events_after=events_after)


@router.get('/{fight_id}', response_model=FightStateResponse)
async def get_fight_state(
    fight_id: UUID,
    context: Annotated[ActiveCharacterContext, Depends(get_active_character_context)],
    fight_service: Annotated[FightService, Depends(get_fight_service)],
    events_after: Annotated[int, Query(ge=0)] = 0,
) -> FightStateResponse:
    return await fight_service.get_state(
        fight_id=fight_id,
        character_id=context.character_id,
        events_after=events_after,
    )


@router.post('/{fight_id}/actions', response_model=FightActionResponse)
async def perform_fight_action(
    fight_id: UUID,
    payload: PerformFightActionRequest,
    context: Annotated[ActiveCharacterContext, Depends(get_active_character_context)],
    fight_service: Annotated[FightService, Depends(get_fight_service)],
) -> FightActionResponse:
    return await fight_service.perform_action(
        fight_id=fight_id,
        character_id=context.character_id,
        idempotency_key=payload.idempotency_key,
        expected_version=payload.expected_version,
        action_code=payload.action_code,
        target_participant_id=payload.target_participant_id,
    )

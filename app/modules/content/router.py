from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_unit_of_work
from app.container import Repositories
from app.modules.content.schemas import ActionDefinitionResponse, EffectDefinitionResponse

router = APIRouter(prefix='/api/v1', tags=['content'])


@router.get('/action-definitions', response_model=list[ActionDefinitionResponse])
async def list_action_definitions(
    repositories: Annotated[Repositories, Depends(get_unit_of_work)],
) -> list[ActionDefinitionResponse]:
    actions = await repositories.action_definitions.search(is_active=True, is_archived=False, order_by='code')
    return [ActionDefinitionResponse.model_validate(action) for action in actions]


@router.get('/effect-definitions', response_model=list[EffectDefinitionResponse])
async def list_effect_definitions(
    repositories: Annotated[Repositories, Depends(get_unit_of_work)],
) -> list[EffectDefinitionResponse]:
    effects = await repositories.effect_definitions.search(is_active=True, is_archived=False, order_by='code')
    return [EffectDefinitionResponse.model_validate(effect) for effect in effects]

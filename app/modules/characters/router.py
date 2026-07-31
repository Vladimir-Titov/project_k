from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    get_character_service,
    get_game_context_service,
    get_locked_session_context,
    get_session_context,
)
from app.modules.characters.schemas import CharacterResponse, CreateCharacterRequest
from app.modules.characters.service import CharacterService
from app.modules.game_context.service import GameContextService, SessionContext

router = APIRouter(prefix='/api/v1/characters', tags=['characters'])


@router.post('', response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    payload: CreateCharacterRequest,
    session_context: Annotated[SessionContext, Depends(get_locked_session_context)],
    character_service: Annotated[CharacterService, Depends(get_character_service)],
) -> CharacterResponse:
    character = await character_service.create(
        account_id=session_context.account_id,
        nickname=payload.nickname,
    )
    return CharacterResponse.from_character(character, is_active=False)


@router.get('', response_model=list[CharacterResponse])
async def list_characters(
    session_context: Annotated[SessionContext, Depends(get_session_context)],
    character_service: Annotated[CharacterService, Depends(get_character_service)],
) -> list[CharacterResponse]:
    characters = await character_service.list(account_id=session_context.account_id)
    return [
        CharacterResponse.from_character(
            character,
            is_active=character.id == session_context.active_character_id,
        )
        for character in characters
    ]


@router.post('/{character_id}/select', response_model=CharacterResponse)
async def select_character(
    character_id: UUID,
    session_context: Annotated[SessionContext, Depends(get_locked_session_context)],
    context_service: Annotated[GameContextService, Depends(get_game_context_service)],
) -> CharacterResponse:
    character = await context_service.select_character(
        context=session_context,
        character_id=character_id,
    )
    return CharacterResponse.from_character(character, is_active=True)

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    get_character_service,
    get_game_context_service,
    get_locked_session_context,
    get_session_context,
)
from app.modules.characters.schemas import (
    CharacterClassResponse,
    CharacterResponse,
    CreateCharacterRequest,
    StatValueResponse,
)
from app.modules.characters.service import CharacterService
from app.modules.game_context.service import GameContextService, SessionContext

router = APIRouter(prefix='/api/v1/characters', tags=['characters'])
classes_router = APIRouter(prefix='/api/v1/character-classes', tags=['character classes'])


@classes_router.get('', response_model=list[CharacterClassResponse])
async def list_character_classes(
    character_service: Annotated[CharacterService, Depends(get_character_service)],
) -> list[CharacterClassResponse]:
    return await character_service.list_classes()


@router.post('', response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    payload: CreateCharacterRequest,
    session_context: Annotated[SessionContext, Depends(get_locked_session_context)],
    character_service: Annotated[CharacterService, Depends(get_character_service)],
) -> CharacterResponse:
    character, character_class = await character_service.create(
        account_id=session_context.account_id,
        nickname=payload.nickname,
        class_code=payload.class_code,
    )
    return CharacterResponse.from_character(character, class_code=character_class.code, is_active=False)


@router.get('', response_model=list[CharacterResponse])
async def list_characters(
    session_context: Annotated[SessionContext, Depends(get_session_context)],
    character_service: Annotated[CharacterService, Depends(get_character_service)],
) -> list[CharacterResponse]:
    characters = await character_service.list(account_id=session_context.account_id)
    return [
        CharacterResponse.from_character(
            character,
            class_code=character_class.code,
            is_active=character.id == session_context.active_character_id,
        )
        for character, character_class in characters
    ]


@router.get('/{character_id}/stats', response_model=list[StatValueResponse])
async def list_character_stats(
    character_id: UUID,
    session_context: Annotated[SessionContext, Depends(get_session_context)],
    character_service: Annotated[CharacterService, Depends(get_character_service)],
) -> list[StatValueResponse]:
    return await character_service.list_stats(character_id=character_id, account_id=session_context.account_id)


@router.post('/{character_id}/rest', response_model=list[StatValueResponse])
async def rest_character(
    character_id: UUID,
    session_context: Annotated[SessionContext, Depends(get_locked_session_context)],
    character_service: Annotated[CharacterService, Depends(get_character_service)],
) -> list[StatValueResponse]:
    return await character_service.rest(character_id=character_id, account_id=session_context.account_id)


@router.post('/{character_id}/select', response_model=CharacterResponse)
async def select_character(
    character_id: UUID,
    session_context: Annotated[SessionContext, Depends(get_locked_session_context)],
    context_service: Annotated[GameContextService, Depends(get_game_context_service)],
    character_service: Annotated[CharacterService, Depends(get_character_service)],
) -> CharacterResponse:
    character = await context_service.select_character(context=session_context, character_id=character_id)
    character_class = await character_service.repositories.character_classes.get_by_id(character.class_id)
    if character_class is None:
        raise RuntimeError('Character class is missing')
    return CharacterResponse.from_character(character, class_code=character_class.code, is_active=True)

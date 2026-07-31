from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_character_service,
    get_current_account_token_payload,
)
from app.modules.auth.service import AccountTokenPayload
from app.modules.characters.exceptions import (
    CharacterAlreadyExistsError,
    CharacterNotFoundError,
    InvalidGameSessionError,
    NicknameAlreadyExistsError,
)
from app.modules.characters.schemas import (
    CharacterResponse,
    CreateCharacterRequest,
)
from app.modules.characters.service import CharacterService

router = APIRouter(prefix='/api/v1/characters', tags=['characters'])


@router.post(
    '',
    response_model=CharacterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_character(
    payload: CreateCharacterRequest,
    token_payload: Annotated[
        AccountTokenPayload,
        Depends(get_current_account_token_payload),
    ],
    character_service: Annotated[
        CharacterService,
        Depends(get_character_service),
    ],
) -> CharacterResponse:
    try:
        selection = await character_service.create(
            account_id=token_payload.account_id,
            session_id=token_payload.session_id,
            nickname=payload.nickname,
        )
    except InvalidGameSessionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='invalid_or_expired_session',
        )
    except CharacterAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='character_already_exists',
        )
    except NicknameAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='nickname_already_exists',
        )
    return CharacterResponse.from_selection(selection)


@router.get('', response_model=list[CharacterResponse])
async def list_characters(
    token_payload: Annotated[
        AccountTokenPayload,
        Depends(get_current_account_token_payload),
    ],
    character_service: Annotated[
        CharacterService,
        Depends(get_character_service),
    ],
) -> list[CharacterResponse]:
    try:
        selections = await character_service.list_for_session(
            account_id=token_payload.account_id,
            session_id=token_payload.session_id,
        )
    except InvalidGameSessionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='invalid_or_expired_session',
        )
    return [
        CharacterResponse.from_selection(selection)
        for selection in selections
    ]


@router.post('/{character_id}/select', response_model=CharacterResponse)
async def select_character(
    character_id: UUID,
    token_payload: Annotated[
        AccountTokenPayload,
        Depends(get_current_account_token_payload),
    ],
    character_service: Annotated[
        CharacterService,
        Depends(get_character_service),
    ],
) -> CharacterResponse:
    try:
        selection = await character_service.select(
            account_id=token_payload.account_id,
            session_id=token_payload.session_id,
            character_id=character_id,
        )
    except InvalidGameSessionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='invalid_or_expired_session',
        )
    except CharacterNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='character_not_found',
        )
    return CharacterResponse.from_selection(selection)

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.services import InvalidTokenError, Services
from web.api.auth.schema import LoginRequest, RefreshRequest, TokenPairResponse
from web.api.dependencies import get_services

router = APIRouter(prefix='/api/v1/auth', tags=['auth'])


@router.post('/login', response_model=TokenPairResponse)
async def login(
    payload: LoginRequest,
    services: Annotated[Services, Depends(get_services)],
) -> TokenPairResponse:
    token_pair = services.auth.login(
        payload.login,
        payload.password.get_secret_value(),
    )
    return TokenPairResponse.from_token_pair(token_pair)


@router.post('/refresh', response_model=TokenPairResponse)
async def refresh(
    payload: RefreshRequest,
    services: Annotated[Services, Depends(get_services)],
) -> TokenPairResponse:
    try:
        token_pair = services.auth.refresh(payload.refresh_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or expired refresh token',
        )
    return TokenPairResponse.from_token_pair(token_pair)

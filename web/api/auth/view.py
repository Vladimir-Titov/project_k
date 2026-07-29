from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.services import AuthService, InvalidTokenError
from web.api.auth.schema import LoginRequest, RefreshRequest, TokenPairResponse
from web.api.dependencies import get_auth_service

router = APIRouter(prefix='/api/v1/auth', tags=['auth'])


@router.post('/login', response_model=TokenPairResponse)
async def login(
    payload: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPairResponse:
    token_pair = auth_service.login(
        payload.login,
        payload.password.get_secret_value(),
    )
    return TokenPairResponse.from_token_pair(token_pair)


@router.post('/refresh', response_model=TokenPairResponse)
async def refresh(
    payload: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPairResponse:
    try:
        token_pair = auth_service.refresh(payload.refresh_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or expired refresh token',
        )
    return TokenPairResponse.from_token_pair(token_pair)

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import (
    get_auth_service,
    get_current_account_token_payload,
)
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
)
from app.modules.auth.service import AccountTokenPayload, AuthService

router = APIRouter(prefix='/api/v1/auth', tags=['auth'])


@router.post(
    '/register',
    response_model=TokenPairResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPairResponse:
    token_pair = await auth_service.register(
        payload.login,
        payload.password.get_secret_value(),
        ip_address=request.client.host if request.client is not None else None,
        user_agent=request.headers.get('user-agent'),
    )
    return TokenPairResponse.from_token_pair(token_pair)


@router.post('/login', response_model=TokenPairResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPairResponse:
    token_pair = await auth_service.login(
        payload.login,
        payload.password.get_secret_value(),
        ip_address=request.client.host if request.client is not None else None,
        user_agent=request.headers.get('user-agent'),
    )
    return TokenPairResponse.from_token_pair(token_pair)


@router.post('/refresh', response_model=TokenPairResponse)
async def refresh(
    payload: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPairResponse:
    token_pair = await auth_service.refresh(payload.refresh_token)
    return TokenPairResponse.from_token_pair(token_pair)


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token_payload: Annotated[
        AccountTokenPayload,
        Depends(get_current_account_token_payload),
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    await auth_service.logout(token_payload.session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

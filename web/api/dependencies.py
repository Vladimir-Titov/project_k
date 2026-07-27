from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services import InvalidTokenError, Services, UserTokenPayload

bearer_scheme = HTTPBearer(auto_error=False)


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_current_user_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    services: Annotated[Services, Depends(get_services)],
) -> UserTokenPayload:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Not authenticated',
        )

    try:
        return services.auth.authenticate_access_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or expired access token',
        )

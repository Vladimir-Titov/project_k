from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import jwt

from settings import AuthConfig


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be trusted for the requested operation."""


class TokenType(StrEnum):
    ACCESS = 'access'
    REFRESH = 'refresh'


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class UserTokenPayload:
    character_id: UUID


class AuthService:
    def __init__(self, config: AuthConfig) -> None:
        self.config = config

    def login(self, login: str, password: str) -> TokenPair:
        """Issue tokens for the temporary authentication stub."""

        if not login or not password:
            raise ValueError('login and password must not be empty')
        character_id = uuid5(NAMESPACE_URL, f'{self.config.issuer}:character:{login}')
        return self._create_token_pair(character_id)

    def refresh(self, refresh_token: str) -> TokenPair:
        character_id = self._decode_subject(refresh_token, TokenType.REFRESH)
        return self._create_token_pair(character_id)

    def authenticate_access_token(self, access_token: str) -> UserTokenPayload:
        character_id = self._decode_subject(access_token, TokenType.ACCESS)
        return UserTokenPayload(character_id=character_id)

    def _create_token_pair(self, character_id: UUID) -> TokenPair:
        now = datetime.now(UTC)
        access_ttl = timedelta(minutes=self.config.access_token_ttl_minutes)
        refresh_ttl = timedelta(days=self.config.refresh_token_ttl_days)
        return TokenPair(
            access_token=self._encode(character_id, TokenType.ACCESS, now, access_ttl),
            refresh_token=self._encode(character_id, TokenType.REFRESH, now, refresh_ttl),
            expires_in=int(access_ttl.total_seconds()),
        )

    def _encode(
        self,
        character_id: UUID,
        token_type: TokenType,
        issued_at: datetime,
        ttl: timedelta,
    ) -> str:
        payload = {
            'sub': str(character_id),
            'token_type': token_type.value,
            'iat': issued_at,
            'exp': issued_at + ttl,
            'iss': self.config.issuer,
            'aud': self.config.audience,
            'jti': str(uuid4()),
        }
        return jwt.encode(
            payload,
            self.config.secret_key.get_secret_value(),
            algorithm=self.config.algorithm,
        )

    def _decode_subject(self, token: str, expected_type: TokenType) -> UUID:
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self.config.secret_key.get_secret_value(),
                algorithms=[self.config.algorithm],
                issuer=self.config.issuer,
                audience=self.config.audience,
                options={
                    'require': [
                        'sub',
                        'token_type',
                        'iat',
                        'exp',
                        'iss',
                        'aud',
                        'jti',
                    ],
                },
            )
        except jwt.PyJWTError as error:
            raise InvalidTokenError('Invalid or expired token') from error

        if payload.get('token_type') != expected_type:
            raise InvalidTokenError(f'Expected a {expected_type} token')

        try:
            return UUID(payload['sub'])
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidTokenError('Invalid or expired token') from error

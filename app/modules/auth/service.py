from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from hmac import compare_digest
from typing import Any
from uuid import UUID, uuid4

import jwt

from app.container import Repositories
from app.core.config import AuthConfig
from app.modules.auth.exceptions import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    InvalidTokenError,
    LoginAlreadyExistsError,
)
from app.modules.auth.models import Session
from app.modules.auth.passwords import PasswordHasher


class TokenType(StrEnum):
    ACCESS = 'access'
    REFRESH = 'refresh'


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class AccountTokenPayload:
    account_id: UUID
    session_id: UUID


@dataclass(frozen=True, slots=True)
class TokenClaims:
    account_id: UUID
    session_id: UUID


class AuthService:
    def __init__(
        self,
        config: AuthConfig,
        repositories: Repositories,
        password_hasher: PasswordHasher,
    ) -> None:
        self.config = config
        self.repositories = repositories
        self.password_hasher = password_hasher

    async def register(
        self,
        login: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        if await self.repositories.accounts.get_by_login(login) is not None:
            raise LoginAlreadyExistsError

        password_hash = await self.password_hasher.hash(password)
        async with self.repositories.transaction() as repositories:
            account = await repositories.accounts.create_if_login_available(
                login=login,
                password_hash=password_hash,
            )
            if account is None:
                raise LoginAlreadyExistsError from None

            return await self._create_session_token_pair(
                repositories=repositories,
                account_id=account.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

    async def login(
        self,
        login: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        account = await self.repositories.accounts.get_active_by_login(login)
        if account is None:
            await self.password_hasher.verify_dummy(password)
            raise InvalidCredentialsError
        if not await self.password_hasher.verify(
            password,
            account.password_hash,
        ):
            raise InvalidCredentialsError

        return await self._create_session_token_pair(
            repositories=self.repositories,
            account_id=account.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def _create_session_token_pair(
        self,
        *,
        repositories: Repositories,
        account_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        now = datetime.now(UTC)
        session = Session(
            account_id=account_id,
            active_character_id=None,
            refresh_token_hash='',
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=now + timedelta(days=self.config.refresh_token_ttl_days),
        )
        token_pair = self._create_token_pair(
            account_id=account_id,
            session_id=session.id,
            session_expires_at=session.expires_at,
            issued_at=now,
        )
        session.refresh_token_hash = self._hash_refresh_token(
            token_pair.refresh_token,
        )
        await repositories.sessions.create_session(session)
        return token_pair

    async def refresh(self, refresh_token: str) -> TokenPair:
        try:
            claims = self._decode_claims(refresh_token, TokenType.REFRESH)
        except InvalidTokenError as error:
            raise InvalidRefreshTokenError('Invalid or expired token') from error
        now = datetime.now(UTC)

        async with self.repositories.transaction() as repositories:
            session = await repositories.sessions.get_for_refresh_for_update(
                claims.session_id,
            )
            if session is None:
                raise InvalidRefreshTokenError('Invalid or expired token')

            valid_session = (
                session.account_id == claims.account_id
                and session.expires_at > now
                and compare_digest(
                    session.refresh_token_hash,
                    self._hash_refresh_token(refresh_token),
                )
            )
            if not valid_session:
                raise InvalidRefreshTokenError('Invalid or expired token')

            token_pair = self._create_token_pair(
                account_id=session.account_id,
                session_id=session.id,
                session_expires_at=session.expires_at,
                issued_at=now,
            )
            await repositories.sessions.replace_refresh_token_hash(
                session.id,
                self._hash_refresh_token(token_pair.refresh_token),
            )
        return token_pair

    async def logout(self, session_id: UUID) -> None:
        await self.repositories.sessions.delete_by_id(session_id)

    def authenticate_access_token(
        self,
        access_token: str,
    ) -> AccountTokenPayload:
        try:
            claims = self._decode_claims(access_token, TokenType.ACCESS)
        except InvalidTokenError as error:
            raise InvalidAccessTokenError('Invalid or expired token') from error
        return AccountTokenPayload(
            account_id=claims.account_id,
            session_id=claims.session_id,
        )

    def _create_token_pair(
        self,
        *,
        account_id: UUID,
        session_id: UUID,
        session_expires_at: datetime,
        issued_at: datetime,
    ) -> TokenPair:
        access_expires_at = min(
            issued_at + timedelta(days=self.config.access_token_ttl_days),
            session_expires_at,
        )
        return TokenPair(
            access_token=self._encode(
                account_id=account_id,
                session_id=session_id,
                token_type=TokenType.ACCESS,
                issued_at=issued_at,
                expires_at=access_expires_at,
            ),
            refresh_token=self._encode(
                account_id=account_id,
                session_id=session_id,
                token_type=TokenType.REFRESH,
                issued_at=issued_at,
                expires_at=session_expires_at,
            ),
            expires_in=int((access_expires_at - issued_at).total_seconds()),
        )

    def _encode(
        self,
        *,
        account_id: UUID,
        session_id: UUID,
        token_type: TokenType,
        issued_at: datetime,
        expires_at: datetime,
    ) -> str:
        payload = {
            'sub': str(account_id),
            'account_id': str(account_id),
            'session_id': str(session_id),
            'token_type': token_type.value,
            'iat': issued_at,
            'exp': expires_at,
            'iss': self.config.issuer,
            'aud': self.config.audience,
            'jti': str(uuid4()),
        }
        return jwt.encode(
            payload,
            self.config.secret_key.get_secret_value(),
            algorithm=self.config.algorithm,
        )

    def _decode_claims(
        self,
        token: str,
        expected_type: TokenType,
    ) -> TokenClaims:
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
                        'account_id',
                        'session_id',
                        'token_type',
                        'iat',
                        'exp',
                        'iss',
                        'aud',
                        'jti',
                    ],
                },
            )
            account_id = UUID(payload['account_id'])
            claims = TokenClaims(
                account_id=account_id,
                session_id=UUID(payload['session_id']),
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
            raise InvalidTokenError('Invalid or expired token') from error

        if payload.get('token_type') != expected_type.value:
            raise InvalidTokenError(f'Expected a {expected_type} token')
        if payload['sub'] != str(account_id):
            raise InvalidTokenError('Invalid or expired token')
        return claims

    @staticmethod
    def _hash_refresh_token(refresh_token: str) -> str:
        return sha256(refresh_token.encode()).hexdigest()

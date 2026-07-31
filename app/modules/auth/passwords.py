from anyio import to_thread
from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2 import Type
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import AuthConfig


class PasswordHasher:
    _DUMMY_PASSWORD = 'project-k-dummy-password'
    _MINIMUM_SALT_BYTES = 8

    def __init__(self, config: AuthConfig) -> None:
        self._salt = config.password_salt.get_secret_value().encode()
        if len(self._salt) < self._MINIMUM_SALT_BYTES:
            raise ValueError('password salt must contain at least 8 bytes')
        self._hasher = Argon2PasswordHasher(type=Type.ID)
        self._dummy_hash = self._hash_sync(self._DUMMY_PASSWORD)

    def _hash_sync(self, password: str) -> str:
        return self._hasher.hash(password, salt=self._salt)

    def _verify_sync(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError):
            return False

    async def hash(self, password: str) -> str:
        return await to_thread.run_sync(self._hash_sync, password)

    async def verify(self, password: str, password_hash: str) -> bool:
        return await to_thread.run_sync(
            self._verify_sync,
            password,
            password_hash,
        )

    async def verify_dummy(self, password: str) -> None:
        await self.verify(password, self._dummy_hash)

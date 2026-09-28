from typing import Protocol


class FileStorageError(Exception):
    pass


class FileRepository(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    def public_url(self, key: str) -> str: ...

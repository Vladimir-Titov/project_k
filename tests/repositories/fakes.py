from collections.abc import Iterable, Sequence
from typing import Any


class FakeContext:
    def __init__(self, value: Any, events: list[str] | None = None, name: str = 'context') -> None:
        self.value = value
        self.events = events
        self.name = name

    async def __aenter__(self) -> Any:
        if self.events is not None:
            self.events.append(f'{self.name}:enter')
        return self.value

    async def __aexit__(self, *_args: object) -> None:
        if self.events is not None:
            self.events.append(f'{self.name}:exit')


class FakeConnection:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []
        self.fetch_result: list[dict[str, Any]] = []
        self.fetchrow_result: dict[str, Any] | None = None
        self.fetchval_result: Any = None

    def transaction(self) -> FakeContext:
        return FakeContext(None, self.events, 'transaction')

    async def execute(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> str:
        del timeout
        self.calls.append(('execute', query, args))
        return 'OK'

    async def executemany(
        self,
        query: str,
        args: Iterable[Sequence[Any]],
        *,
        timeout: float | None = None,
    ) -> None:
        del timeout
        self.calls.append(('executemany', query, tuple(tuple(item) for item in args)))

    async def fetch(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        del timeout
        self.calls.append(('fetch', query, args))
        return self.fetch_result

    async def fetchrow(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> dict[str, Any] | None:
        del timeout
        self.calls.append(('fetchrow', query, args))
        return self.fetchrow_result

    async def fetchval(
        self,
        query: str,
        *args: Any,
        column: int = 0,
        timeout: float | None = None,
    ) -> Any:
        del column, timeout
        self.calls.append(('fetchval', query, args))
        return self.fetchval_result


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.acquire_count = 0

    def acquire(self) -> FakeContext:
        self.acquire_count += 1
        return FakeContext(self.connection, self.connection.events, 'connection')

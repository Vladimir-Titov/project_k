from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI

from app.lifespans import compose_lifespans
from app.lifespans.base import Lifespan


def tracked_lifespan(name: str, events: list[str]) -> Lifespan:
    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        events.append(f'{name}:started')
        try:
            yield
        finally:
            events.append(f'{name}:stopped')

    return lifespan


@pytest.mark.asyncio
async def test_lifespans_start_in_order_and_stop_in_reverse_order() -> None:
    events: list[str] = []
    lifespan = compose_lifespans(
        tracked_lifespan('database', events),
        tracked_lifespan('future-resource', events),
    )

    async with lifespan(FastAPI()):
        events.append('application:running')

    assert events == [
        'database:started',
        'future-resource:started',
        'application:running',
        'future-resource:stopped',
        'database:stopped',
    ]

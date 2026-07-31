"""Composable FastAPI lifespan primitives."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

type Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def compose_lifespans(*lifespans: Lifespan) -> Lifespan:
    """Compose independent resources in startup order and close them in reverse order."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for resource_lifespan in lifespans:
                await stack.enter_async_context(resource_lifespan(application))
            yield

    return lifespan

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from web.lifespans.base import Lifespan


def create_admin_lifespan(engine: AsyncEngine) -> Lifespan:
    @asynccontextmanager
    async def admin_lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.admin_engine = engine
        try:
            yield
        finally:
            await engine.dispose()
            del application.state.admin_engine

    return admin_lifespan

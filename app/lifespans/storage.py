from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.files.s3 import S3FileRepository
from app.lifespans.base import Lifespan


def create_storage_lifespan(files: S3FileRepository) -> Lifespan:
    @asynccontextmanager
    async def storage_lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            if files.config.initialize_local_bucket:
                await files.initialize_local_bucket()
            application.state.files = files
            yield
        finally:
            await files.close()
            if hasattr(application.state, 'files'):
                del application.state.files

    return storage_lifespan

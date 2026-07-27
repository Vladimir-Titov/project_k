from fastapi import APIRouter

from web.api.auth import router as auth_router
from web.api.default.default import router as default_router
from web.api.fights import router as fights_router


def create_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(default_router)
    router.include_router(auth_router)
    router.include_router(fights_router)
    return router

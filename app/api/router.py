from fastapi import APIRouter

from app.api.health import router as default_router
from app.modules.auth.router import router as auth_router
from app.modules.battles.router import router as fights_router
from app.modules.characters.router import router as characters_router


def create_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(default_router)
    router.include_router(auth_router)
    router.include_router(characters_router)
    router.include_router(fights_router)
    return router

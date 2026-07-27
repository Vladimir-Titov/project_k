from fastapi import APIRouter

from web.api.default.default import router as default_router


def create_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(default_router)
    return router

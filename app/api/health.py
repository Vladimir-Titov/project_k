"""Application health endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=['default'])


@router.get('/')
async def root() -> dict[str, str]:
    return {'message': 'Hello World'}


@router.get('/hello/{name}')
async def say_hello(name: str) -> dict[str, str]:
    return {'message': f'Hello {name}'}

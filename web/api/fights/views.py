from fastapi import APIRouter

router = APIRouter(prefix='fights', tags=['fights'])


@router.get('/')
async def create_fight() -> dict[str, str]:
    return {'message': 'Hello World'}

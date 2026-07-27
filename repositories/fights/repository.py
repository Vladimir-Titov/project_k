from app.models.fights import Fight
from repositories.entity import EntityRepository


class FightRepository(EntityRepository[Fight]):
    entity = Fight

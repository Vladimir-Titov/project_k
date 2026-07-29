from app.models import Character, Mob
from app.models.fights import Fight
from repositories.entity import EntityRepository


class FightRepository(EntityRepository[Fight]):
    entity = Fight


class CharacterRepository(EntityRepository[Character]):
    entity = Character


class MobRepository(EntityRepository[Mob]):
    entity = Mob

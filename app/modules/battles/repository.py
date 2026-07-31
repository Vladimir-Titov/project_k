from app.core.db.entity_repository import EntityRepository
from app.modules.battles.models import Fight, FightParticipants


class FightRepository(EntityRepository[Fight]):
    entity = Fight


class FightParticipantRepository(EntityRepository[FightParticipants]):
    entity = FightParticipants

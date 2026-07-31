from app.core.db.entity_repository import EntityRepository
from app.modules.monsters.models import Mob


class MobRepository(EntityRepository[Mob]):
    entity = Mob

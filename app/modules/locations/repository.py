from app.core.db.entity_repository import EntityRepository
from app.modules.locations.models import Location, LocationTransition


class LocationRepository(EntityRepository[Location]):
    entity = Location


class LocationTransitionRepository(EntityRepository[LocationTransition]):
    entity = LocationTransition

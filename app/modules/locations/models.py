from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, Relationship

from app.core.db.models import TableBase


class Location(TableBase, table=True):
    __tablename__ = 'locations'

    code: str = Field(index=True, unique=True, max_length=64)
    title: str = Field(max_length=128)
    description: str | None = Field(default=None)
    image_url: str | None = Field(default=None, max_length=2048)

    def __admin_repr__(self, _request: Any) -> str:
        return self.title


class LocationTransition(TableBase, table=True):
    __tablename__ = 'location_transitions'
    __table_args__ = (
        UniqueConstraint('from_location_id', 'to_location_id', name='uq_location_transition_pair'),
        CheckConstraint('from_location_id <> to_location_id', name='ck_transition_distinct_locations'),
        CheckConstraint('base_duration_seconds > 0', name='ck_transition_positive_duration'),
    )

    from_location_id: UUID = Field(index=True, foreign_key='frontiers.locations.id')
    to_location_id: UUID = Field(index=True, foreign_key='frontiers.locations.id')
    base_duration_seconds: int = Field(default=30, gt=0)
    is_enabled: bool = Field(default=True)
    from_location: Location = Relationship(
        sa_relationship_kwargs={'foreign_keys': '[LocationTransition.from_location_id]', 'lazy': 'joined'}
    )
    to_location: Location = Relationship(
        sa_relationship_kwargs={'foreign_keys': '[LocationTransition.to_location_id]', 'lazy': 'joined'}
    )

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.from_location.title} → {self.to_location.title}'

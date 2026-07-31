from typing import TYPE_CHECKING, Any

from sqlmodel import Field, Relationship

from app.core.db.models import TableBase

if TYPE_CHECKING:
    from app.modules.battles.models import FightParticipants


class Mob(TableBase, table=True):
    __tablename__ = 'mobs'

    title: str = Field(index=True, nullable=False)
    fight_participations: list[FightParticipants] = Relationship(
        back_populates='mob',
    )

    def __admin_repr__(self, _request: Any) -> str:
        return self.title

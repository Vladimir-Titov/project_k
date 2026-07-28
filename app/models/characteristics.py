from typing import TYPE_CHECKING, Any

from sqlmodel import Field, Relationship

from app.models.base import TableBase

if TYPE_CHECKING:
    from app.models.characteristics_actions import CharacteristicsActions


class Characteristics(TableBase, table=True):
    title: str = Field(nullable=False)
    value: int = Field(nullable=False)
    description: str = Field(nullable=True)
    action_links: list[CharacteristicsActions] = Relationship(
        back_populates='characteristic',
    )

    def __admin_repr__(self, _request: Any) -> str:
        return self.title

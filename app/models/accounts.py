from typing import TYPE_CHECKING, Any

from sqlmodel import Field, Relationship

from app.models.base import TableBase

if TYPE_CHECKING:
    from app.models.characters import Character


class Account(TableBase, table=True):
    login: str = Field(index=True, nullable=False)
    password: str = Field(nullable=False)
    character: Character = Relationship(
        back_populates='account',
        sa_relationship_kwargs={'uselist': False},
    )

    def __admin_repr__(self, _request: Any) -> str:
        return self.login

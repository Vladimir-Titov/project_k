from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Column, Text
from sqlmodel import Field, Relationship

from app.core.db.models import TableBase, UTCDateTime

if TYPE_CHECKING:
    from app.modules.characters.models import Character


class Account(TableBase, table=True):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'auth'}

    login: str = Field(index=True, unique=True, nullable=False, max_length=64)
    password_hash: str = Field(nullable=False, max_length=512)
    character: Character = Relationship(
        back_populates='account',
        sa_relationship_kwargs={'uselist': False},
    )
    sessions: list[Session] = Relationship(back_populates='account')

    def __admin_repr__(self, _request: Any) -> str:
        return self.login


class Session(TableBase, table=True):
    __tablename__ = 'sessions'
    __table_args__ = {'schema': 'auth'}

    account_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='auth.users.id',
    )
    active_character_id: UUID | None = Field(
        default=None,
        index=True,
        nullable=True,
        foreign_key='frontiers.characters.id',
    )
    refresh_token_hash: str = Field(
        index=True,
        unique=True,
        nullable=False,
        max_length=64,
    )
    ip_address: str | None = Field(default=None, nullable=True, max_length=45)
    user_agent: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    expires_at: datetime = Field(nullable=False, sa_type=UTCDateTime)
    account: Account = Relationship(back_populates='sessions')

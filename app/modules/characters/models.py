from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Column, Numeric, UniqueConstraint
from sqlmodel import Field, Relationship

from app.core.db.models import TableBase

if TYPE_CHECKING:
    from app.modules.auth.models import Account
    from app.modules.content.models import ActionDefinition
    from app.modules.stats.models import StatDefinition


class CharacterClass(TableBase, table=True):
    __tablename__ = 'character_classes'

    code: str = Field(index=True, unique=True, nullable=False, max_length=64)
    title: str = Field(nullable=False, max_length=128)
    description: str | None = Field(default=None, nullable=True, max_length=512)
    is_playable: bool = Field(default=True, nullable=False)

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.title} ({self.code})'


class ClassStat(TableBase, table=True):
    __tablename__ = 'class_stats'
    __table_args__ = (UniqueConstraint('class_id', 'stat_definition_id', name='uq_class_stat_pair'),)

    class_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.character_classes.id')
    stat_definition_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='frontiers.stat_definitions.id',
    )
    value: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False))
    character_class: CharacterClass = Relationship()
    stat_definition: StatDefinition = Relationship()


class ClassAction(TableBase, table=True):
    __tablename__ = 'class_actions'
    __table_args__ = (UniqueConstraint('class_id', 'action_definition_id', name='uq_class_action_pair'),)

    class_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.character_classes.id')
    action_definition_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='frontiers.action_definitions.id',
    )
    character_class: CharacterClass = Relationship()
    action_definition: ActionDefinition = Relationship()


class Character(TableBase, table=True):
    __tablename__ = 'characters'

    account_id: UUID = Field(
        index=True,
        unique=True,
        nullable=False,
        foreign_key='auth.users.id',
    )
    nickname: str = Field(
        index=True,
        unique=True,
        nullable=False,
        max_length=64,
    )
    class_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='frontiers.character_classes.id',
    )
    account: Account = Relationship(back_populates='character')
    character_class: CharacterClass = Relationship()

    def __admin_repr__(self, _request: Any) -> str:
        return self.nickname


class CharacterStat(TableBase, table=True):
    __tablename__ = 'character_stats'
    __table_args__ = (UniqueConstraint('character_id', 'stat_definition_id', name='uq_character_stat_pair'),)

    character_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.characters.id')
    stat_definition_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='frontiers.stat_definitions.id',
    )
    value: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False))
    character: Character = Relationship()
    stat_definition: StatDefinition = Relationship()


class CharacterAction(TableBase, table=True):
    __tablename__ = 'character_actions'
    __table_args__ = (UniqueConstraint('character_id', 'action_definition_id', name='uq_character_action_pair'),)

    character_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.characters.id')
    action_definition_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='frontiers.action_definitions.id',
    )
    character: Character = Relationship()
    action_definition: ActionDefinition = Relationship()

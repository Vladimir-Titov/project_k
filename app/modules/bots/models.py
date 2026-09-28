from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Column, Numeric, UniqueConstraint
from sqlmodel import Field, Relationship

from app.core.db.models import TableBase

if TYPE_CHECKING:
    from app.modules.content.models import ActionDefinition
    from app.modules.stats.models import StatDefinition


class BotTemplate(TableBase, table=True):
    __tablename__ = 'bot_templates'

    code: str = Field(index=True, unique=True, nullable=False, max_length=64)
    title: str = Field(nullable=False, max_length=128)
    description: str | None = Field(default=None, nullable=True, max_length=512)
    is_active: bool = Field(default=False, nullable=False)

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.title} ({self.code})'


class BotTemplateStat(TableBase, table=True):
    __tablename__ = 'bot_template_stats'
    __table_args__ = (UniqueConstraint('bot_template_id', 'stat_definition_id', name='uq_bot_template_stat_pair'),)

    bot_template_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.bot_templates.id')
    stat_definition_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.stat_definitions.id')
    value: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False))
    bot_template: BotTemplate = Relationship()
    stat_definition: StatDefinition = Relationship()

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.bot_template.title}: {self.stat_definition.title} = {self.value}'


class BotTemplateAction(TableBase, table=True):
    __tablename__ = 'bot_template_actions'
    __table_args__ = (UniqueConstraint('bot_template_id', 'action_definition_id', name='uq_bot_template_action_pair'),)

    bot_template_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.bot_templates.id')
    action_definition_id: UUID = Field(index=True, nullable=False, foreign_key='frontiers.action_definitions.id')
    priority: int = Field(default=0, nullable=False)
    bot_template: BotTemplate = Relationship()
    action_definition: ActionDefinition = Relationship()

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.bot_template.title}: {self.action_definition.title}'

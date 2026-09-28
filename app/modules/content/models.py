from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Column, Enum, Text, UniqueConstraint
from sqlmodel import Field, Relationship

from app.core.db.models import TableBase
from app.modules.content.enums import (
    EffectDuration,
    RuleKind,
    RuleOperation,
    StackingPolicy,
    TargetPolicy,
)

if TYPE_CHECKING:
    from app.modules.stats.models import StatDefinition


def enum_column(enum: type[Any], name: str) -> Column[Any]:
    return Column(
        Enum(
            enum,
            name=name,
            native_enum=False,
            validate_strings=True,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
    )


class ActionDefinition(TableBase, table=True):
    __tablename__ = 'action_definitions'

    code: str = Field(index=True, unique=True, nullable=False, max_length=64)
    title: str = Field(nullable=False, max_length=128)
    description: str | None = Field(default=None, nullable=True, max_length=512)
    image_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    target_policy: TargetPolicy = Field(sa_column=enum_column(TargetPolicy, 'target_policy'))
    is_active: bool = Field(default=True, nullable=False)

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.title} ({self.code})'


class EffectDefinition(TableBase, table=True):
    __tablename__ = 'effect_definitions'

    code: str = Field(index=True, unique=True, nullable=False, max_length=64)
    title: str = Field(nullable=False, max_length=128)
    description: str | None = Field(default=None, nullable=True, max_length=512)
    image_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    duration: EffectDuration = Field(sa_column=enum_column(EffectDuration, 'effect_duration'))
    duration_turns: int | None = Field(default=None, nullable=True)
    stacking_policy: StackingPolicy = Field(
        default=StackingPolicy.REFRESH,
        sa_column=enum_column(StackingPolicy, 'stacking_policy'),
    )
    is_active: bool = Field(default=True, nullable=False)

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.title} ({self.code})'


class EffectRule(TableBase, table=True):
    __tablename__ = 'effect_rules'

    effect_definition_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='frontiers.effect_definitions.id',
    )
    stat_definition_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='frontiers.stat_definitions.id',
    )
    kind: RuleKind = Field(sa_column=enum_column(RuleKind, 'effect_rule_kind'))
    operation: RuleOperation = Field(sa_column=enum_column(RuleOperation, 'effect_rule_operation'))
    evaluator_type: str = Field(default='expression_v1', nullable=False, max_length=32)
    expression: str = Field(sa_column=Column(Text, nullable=False))
    priority: int = Field(default=0, nullable=False)
    effect_definition: EffectDefinition = Relationship()
    stat_definition: StatDefinition = Relationship()


class ActionEffect(TableBase, table=True):
    __tablename__ = 'action_effects'
    __table_args__ = (UniqueConstraint('action_definition_id', 'effect_definition_id', name='uq_action_effect_pair'),)

    action_definition_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='frontiers.action_definitions.id',
    )
    effect_definition_id: UUID = Field(
        index=True,
        nullable=False,
        foreign_key='frontiers.effect_definitions.id',
    )
    target_selector: TargetPolicy = Field(sa_column=enum_column(TargetPolicy, 'effect_target_selector'))
    order: int = Field(default=0, nullable=False)
    action_definition: ActionDefinition = Relationship()
    effect_definition: EffectDefinition = Relationship()

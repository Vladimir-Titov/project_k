from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Column, Enum, Numeric
from sqlmodel import Field

from app.core.db.models import TableBase
from app.modules.stats.enums import StatKind

DECIMAL_COLUMN = Numeric(18, 4)


class StatDefinition(TableBase, table=True):
    __tablename__ = 'stat_definitions'

    code: str = Field(index=True, unique=True, nullable=False, max_length=64)
    title: str = Field(nullable=False, max_length=128)
    description: str | None = Field(default=None, nullable=True, max_length=512)
    kind: StatKind = Field(
        sa_column=Column(
            Enum(
                StatKind,
                name='stat_kind',
                native_enum=False,
                validate_strings=True,
                values_callable=lambda enum: [item.value for item in enum],
            ),
            nullable=False,
        ),
    )
    min_value: Decimal | None = Field(default=None, sa_column=Column(DECIMAL_COLUMN, nullable=True))
    max_value: Decimal | None = Field(default=None, sa_column=Column(DECIMAL_COLUMN, nullable=True))
    max_stat_definition_id: UUID | None = Field(
        default=None,
        nullable=True,
        foreign_key='frontiers.stat_definitions.id',
    )

    def __admin_repr__(self, _request: Any) -> str:
        return f'{self.title} ({self.code})'

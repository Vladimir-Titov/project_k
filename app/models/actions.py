from sqlalchemy import Column, Enum
from sqlmodel import Field

from app.enums.actions import ActionsType
from app.enums.fights import FightStatus
from app.models.base import TableBase


class Actions(TableBase, table=True):
    title: str = Field(nullable=False)
    description: str = Field(nullable=True)
    is_active: bool = Field(
        default=True,
        nullable=False,
    )
    type: ActionsType = Field(
        sa_column=Column(
            Enum(
                FightStatus,
                name='actions_type',
                native_enum=False,
                validate_strings=True,
                values_callable=lambda enum: [item.value for item in enum],
            ),
            nullable=False,
        ),
    )

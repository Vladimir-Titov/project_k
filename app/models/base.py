from datetime import UTC, datetime
from uuid import UUID, uuid7

from sqlalchemy import DateTime, false, func
from sqlmodel import Field, SQLModel


class UTCDateTime(DateTime):
    def __init__(self) -> None:
        super().__init__(timezone=True)


def utc_now() -> datetime:
    return datetime.now(UTC)


class TableBase(SQLModel):
    id: UUID = Field(
        default_factory=uuid7,
        primary_key=True,
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_type=UTCDateTime,
        sa_column_kwargs={
            'server_default': func.now(),
        },
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_type=UTCDateTime,
        sa_column_kwargs={
            'server_default': func.now(),
            'onupdate': func.now(),
        },
    )

    is_archived: bool = Field(
        default=False,
        nullable=False,
        sa_column_kwargs={
            'server_default': false(),
        },
    )

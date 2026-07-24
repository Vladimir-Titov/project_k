from sqlmodel import Field

from app.models.base import TableBase


class Characteristics(TableBase, table=True):
    title: str = Field(nullable=False)
    value: int = Field(nullable=False)
    description: str = Field(nullable=True)

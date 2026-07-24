from sqlmodel import Field

from app.models.base import TableBase


class Account(TableBase, table=True):
    login: str = Field(index=True, nullable=False)
    password: str = Field(nullable=False)

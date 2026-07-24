from sqlmodel import Field

from app.models.base import TableBase


class Mob(TableBase, table=True):
    __tablename__ = 'mobs'

    name: str = Field(index=True, nullable=False)

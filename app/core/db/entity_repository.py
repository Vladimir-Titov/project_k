from copy import deepcopy
from types import NoneType
from typing import Any, ClassVar, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, create_model
from sqlalchemy import Column, func, insert, select
from sqlalchemy.sql import Select

from app.core.db.models import TableBase
from app.core.db.repository import BaseRepository

_SYSTEM_CREATE_FIELDS = frozenset(TableBase.model_fields)
_COMPARISON_SUFFIXES = ('ne', 'gt', 'ge', 'lt', 'le', 'in', 'notin', 'is', 'isnot')
_STRING_SUFFIXES = ('like', 'ilike')


def _optional(annotation: Any) -> Any:
    return annotation if NoneType in get_args(annotation) else annotation | None


def _create_payload_model(entity: type[TableBase]) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    table = entity.__table__

    for name, model_field in entity.model_fields.items():
        if name in _SYSTEM_CREATE_FIELDS:
            continue

        annotation = model_field.annotation
        field_info = deepcopy(model_field)
        column = table.columns.get(name)
        if column is not None and column.nullable and model_field.is_required():
            annotation = _optional(annotation)
            field_info.default = None
        fields[name] = (annotation, field_info)

    return create_model(
        f'{entity.__name__}CreatePayload',
        __config__=ConfigDict(extra='forbid'),
        **fields,
    )


def _create_filter_model(entity: type[TableBase]) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}

    for name, model_field in entity.model_fields.items():
        annotation = model_field.annotation
        optional_annotation = _optional(annotation)
        fields[name] = (optional_annotation, Field(default=None))

        for suffix in _COMPARISON_SUFFIXES:
            filter_annotation = list[annotation] | None if suffix in {'in', 'notin'} else optional_annotation
            fields[f'{name}_{suffix}'] = (filter_annotation, Field(default=None))

        if isinstance(annotation, type) and issubclass(annotation, str):
            for suffix in _STRING_SUFFIXES:
                fields[f'{name}_{suffix}'] = (str | None, Field(default=None))

    return create_model(
        f'{entity.__name__}Filter',
        __config__=ConfigDict(extra='forbid'),
        **fields,
    )


class EntityRepository[EntityT: TableBase](BaseRepository):
    entity: ClassVar[type[TableBase]]
    payload_model: ClassVar[type[BaseModel]]
    filter_model: ClassVar[type[BaseModel]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        entity = getattr(cls, 'entity', None)
        if entity is None:
            return
        if not hasattr(entity, '__table__'):
            raise TypeError(f'{entity.__name__} must be declared with table=True')

        cls.payload_model = _create_payload_model(entity)
        cls.filter_model = _create_filter_model(entity)

    @property
    def table(self) -> Any:
        return self.entity.__table__

    def _to_entity(self, row: dict[str, Any]) -> EntityT:
        return self.entity.model_validate(row)

    def _insert_values(self, payload: BaseModel) -> dict[str, Any]:
        entity = self.entity(**payload.model_dump(mode='python'))
        return {
            column.name: getattr(entity, column.name) for column in self.table.columns if hasattr(entity, column.name)
        }

    def _filter_expression(self, name: str, value: Any) -> Any:
        columns = self.table.columns
        if name in columns:
            column = columns[name]
            return column.is_(None) if value is None else column == value

        column_name, separator, operator = name.rpartition('_')
        if not separator or column_name not in columns:
            raise ValueError(f'Unknown filter: {name}')

        column = columns[column_name]
        operations = {
            'ne': column.__ne__,
            'gt': column.__gt__,
            'ge': column.__ge__,
            'lt': column.__lt__,
            'le': column.__le__,
            'in': column.in_,
            'notin': column.not_in,
            'is': column.is_,
            'isnot': column.is_not,
            'like': column.like,
            'ilike': column.ilike,
        }
        try:
            operation = operations[operator]
        except KeyError:
            raise ValueError(f'Unknown filter operator: {operator}') from None
        return operation(value)

    def _apply_filters(self, query: Select[Any], filters: BaseModel) -> Select[Any]:
        for name, value in filters.model_dump(exclude_unset=True, mode='python').items():
            query = query.where(self._filter_expression(name, value))
        return query

    def _apply_ordering(
        self,
        query: Select[Any],
        order_by: str | list[str] | None,
    ) -> Select[Any]:
        if order_by is None:
            return query

        fields = [order_by] if isinstance(order_by, str) else order_by
        for field in fields:
            descending = field.startswith('-')
            column_name = field[1:] if descending else field
            if column_name not in self.table.columns:
                raise ValueError(f'Unknown order field: {column_name}')
            column: Column[Any] = self.table.columns[column_name]
            query = query.order_by(column.desc() if descending else column.asc())
        return query

    async def create(self, **payload: Any) -> EntityT:
        validated_payload = self.payload_model.model_validate(payload)
        query = insert(self.table).values(self._insert_values(validated_payload)).returning(self.table)
        row = await self.fetchrow(query)
        if row is None:
            raise RuntimeError(f'INSERT into {self.table.name} returned no row')
        return self._to_entity(row)

    async def create_many(self, entities: list[dict[str, Any]]) -> list[EntityT]:
        if not entities:
            return []

        values = [
            self._insert_values(self.payload_model.model_validate(entity))
            for entity in entities
        ]
        query = insert(self.table).values(values).returning(self.table)
        return [self._to_entity(row) for row in await self.fetch(query)]

    async def get_by_id(self, entity_id: UUID) -> EntityT | None:
        primary_key = tuple(self.table.primary_key.columns)
        if len(primary_key) != 1:
            raise RuntimeError(f'{self.table.name} must have exactly one primary key column')

        row = await self.fetchrow(select(self.table).where(primary_key[0] == entity_id))
        return self._to_entity(row) if row is not None else None

    async def search(
        self,
        *,
        order_by: str | list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        **filters: Any,
    ) -> list[EntityT]:
        if limit is not None and limit < 1:
            raise ValueError('limit must be greater than zero')
        if offset < 0:
            raise ValueError('offset must be greater than or equal to zero')

        validated_filters = self.filter_model.model_validate(filters)
        query = self._apply_filters(select(self.table), validated_filters)
        query = self._apply_ordering(query, order_by)
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        return [self._to_entity(row) for row in await self.fetch(query)]

    async def count(self, **filters: Any) -> int:
        validated_filters = self.filter_model.model_validate(filters)
        query = select(func.count()).select_from(self.table)
        query = self._apply_filters(query, validated_filters)
        return int(await self.fetchval(query))

from unittest.mock import Mock

import pytest
from alembic.operations import MigrationScript, ops
from sqlalchemy import Column, Integer
from sqlmodel import Field

from app.models.base import TableBase
from helpers.metadata import DEFAULT_SCHEMA, get_all_metadata, get_metadata, get_registered_schemas
from helpers.migration import add_schema_create_operations
from repositories.entity import EntityRepository
from repositories.query import compile_query


def test_default_metadata_uses_frontiers_schema() -> None:
    metadata = get_metadata()

    assert metadata.schema == 'frontiers'
    assert metadata is get_metadata(DEFAULT_SCHEMA)


def test_metadata_is_cached_per_schema() -> None:
    first = get_metadata('repository_tests')
    second = get_metadata('repository_tests')

    assert first is second
    assert first.schema == 'repository_tests'
    assert first in get_all_metadata()
    assert 'repository_tests' in get_registered_schemas()


@pytest.mark.parametrize(
    'schema',
    ['Battle', 'battle-events', 'battle.events', '1battle', ''],
)
def test_schema_name_is_validated(schema: str) -> None:
    with pytest.raises(ValueError, match='schema must start'):
        get_metadata(schema)


def test_model_and_repository_queries_use_selected_schema() -> None:
    schema_metadata = get_metadata('schema_query_tests')

    class SchemaEntity(TableBase, table=True):
        metadata = schema_metadata
        __tablename__ = 'entities'

        title: str = Field(nullable=False)

    class SchemaRepository(EntityRepository[SchemaEntity]):
        entity = SchemaEntity

    repository = SchemaRepository(Mock())
    query = repository._apply_filters(
        repository.table.select(),
        SchemaRepository.filter_model.model_validate({'title': 'fights'}),
    )
    sql, parameters = compile_query(query)

    assert SchemaEntity.__table__.schema == 'schema_query_tests'
    assert 'FROM schema_query_tests.entities' in sql
    assert 'schema_query_tests.entities.title = $1::VARCHAR' in sql
    assert parameters == ('fights',)


def test_alembic_creates_each_custom_schema_before_its_tables() -> None:
    upgrade_ops = ops.UpgradeOps(
        ops=[
            ops.CreateTableOp(
                'fights',
                [Column('id', Integer, primary_key=True)],
                schema='frontiers',
            ),
            ops.CreateTableOp(
                'fight_actions',
                [Column('id', Integer, primary_key=True)],
                schema='frontiers',
            ),
            ops.CreateTableOp(
                'accounts',
                [Column('id', Integer, primary_key=True)],
            ),
        ],
    )
    migration = MigrationScript(
        '0002',
        upgrade_ops,
        ops.DowngradeOps(ops=[]),
    )

    add_schema_create_operations([migration])
    add_schema_create_operations([migration])

    create_schema_operations = [operation for operation in upgrade_ops.ops if isinstance(operation, ops.ExecuteSQLOp)]
    assert len(create_schema_operations) == 1
    assert create_schema_operations[0].sqltext == 'CREATE SCHEMA IF NOT EXISTS "frontiers"'
    assert upgrade_ops.ops[0] is create_schema_operations[0]
    assert migration.downgrade_ops.ops == []

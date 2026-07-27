from alembic.operations import MigrationScript, ops

from helpers.metadata import POSTGRES_DEFAULT_SCHEMA


def _create_schema_sql(schema: str) -> str:
    quoted_schema = schema.replace('"', '""')
    return f'CREATE SCHEMA IF NOT EXISTS "{quoted_schema}"'


def add_schema_create_operations(directives: list[MigrationScript]) -> None:
    """Create non-public schemas before Alembic creates their first tables.

    Schemas are intentionally not dropped during downgrade: a schema can predate
    the migration or contain objects managed outside this application.
    """

    for script in directives:
        for upgrade_ops in script.upgrade_ops_list:
            schemas = {
                operation.schema
                for operation in upgrade_ops.ops
                if isinstance(operation, ops.CreateTableOp)
                and operation.schema
                and operation.schema != POSTGRES_DEFAULT_SCHEMA
            }
            existing_sql = {
                operation.sqltext for operation in upgrade_ops.ops if isinstance(operation, ops.ExecuteSQLOp)
            }
            create_operations = [
                ops.ExecuteSQLOp(sql)
                for schema in sorted(schemas)
                if (sql := _create_schema_sql(schema)) not in existing_sql
            ]
            upgrade_ops.ops[:0] = create_operations

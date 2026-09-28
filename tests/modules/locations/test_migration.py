import importlib.util
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_migration_renders_schema_seed_and_backfill():
    path = Path(__file__).parents[3] / 'alembic/versions/0002_locations.py'
    spec = importlib.util.spec_from_file_location('locations_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name='postgresql', opts={'as_sql': True, 'literal_binds': True, 'output_buffer': output}
    )
    with Operations.context(context):
        migration.upgrade()
    sql = output.getvalue()
    assert 'CREATE TABLE frontiers.locations' in sql
    assert 'CREATE TABLE frontiers.location_transitions' in sql
    assert 'UPDATE frontiers.characters SET location_id' in sql
    assert 'next_movement_at' in sql
    assert 'movement_speed' in sql
    assert len(migration.LOCATIONS) == 13
    with Operations.context(context):
        migration.downgrade()

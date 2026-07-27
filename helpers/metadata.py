import re
from threading import Lock

from sqlalchemy import MetaData

DEFAULT_SCHEMA = 'frontiers'
POSTGRES_DEFAULT_SCHEMA = 'public'
_SCHEMA_NAME_PATTERN = re.compile(r'^[a-z_][a-z0-9_]*$')
_metadata_lock = Lock()
_metadata_by_schema: dict[str, MetaData] = {
    DEFAULT_SCHEMA: MetaData(schema=DEFAULT_SCHEMA),
}


def get_metadata(schema: str = DEFAULT_SCHEMA) -> MetaData:
    """Return the shared MetaData collection for a PostgreSQL schema.

    Models opt into a schema by assigning the returned object in their class body:

        class Fight(TableBase, table=True):
            metadata = get_metadata('battles')
    """

    if not _SCHEMA_NAME_PATTERN.fullmatch(schema):
        raise ValueError(
            'schema must start with a lowercase letter or underscore and contain '
            'only lowercase letters, digits, and underscores',
        )

    with _metadata_lock:
        metadata = _metadata_by_schema.get(schema)
        if metadata is None:
            metadata = MetaData(schema=schema)
            _metadata_by_schema[schema] = metadata
        return metadata


def get_all_metadata() -> tuple[MetaData, ...]:
    """Return every registered MetaData collection for Alembic autogenerate."""

    with _metadata_lock:
        return tuple(_metadata_by_schema.values())


def get_registered_schemas() -> frozenset[str]:
    with _metadata_lock:
        return frozenset(_metadata_by_schema)

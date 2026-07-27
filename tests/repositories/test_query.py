from sqlalchemy import Column, Integer, MetaData, String, Table, select

from repositories.query import compile_query


def test_compile_query_uses_asyncpg_placeholders_and_parameter_order() -> None:
    table = Table(
        'entities',
        MetaData(),
        Column('id', Integer),
        Column('title', String),
    )
    query = select(table).where(table.c.title == 'fight').where(table.c.id >= 7)

    sql, parameters = compile_query(query)

    assert 'entities.title = $1::VARCHAR' in sql
    assert 'entities.id >= $2::INTEGER' in sql
    assert parameters == ('fight', 7)


def test_compile_query_preserves_raw_asyncpg_query() -> None:
    sql, parameters = compile_query('SELECT $1::INTEGER', (42,))

    assert sql == 'SELECT $1::INTEGER'
    assert parameters == (42,)

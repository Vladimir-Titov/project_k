"""Locations, directed roads and movement cooldown. Existing heroes start in Veldar."""

from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def base_columns():
    return [
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_archived', sa.Boolean(), server_default=sa.false(), nullable=False),
    ]


LOCATIONS = [
    ('00000000-0000-0000-0000-000000009001', 'loc-teren-city', 'Велдар — Медный двор'),
    ('00000000-0000-0000-0000-000000009002', 'loc-sairan-city', 'Велсар — Железный двор'),
    ('00000000-0000-0000-0000-000000009003', 'loc-teren-suburb', 'Нижние сады'),
    ('00000000-0000-0000-0000-000000009004', 'loc-sairan-suburb', 'Нижние дворы'),
    ('00000000-0000-0000-0000-000000009005', 'loc-teren-forest', 'Роща тихих колокольцев'),
    ('00000000-0000-0000-0000-000000009006', 'loc-sairan-forest', 'Роща глухих ветвей'),
    ('00000000-0000-0000-0000-000000009007', 'loc-teren-quarry', 'Белый уступ'),
    ('00000000-0000-0000-0000-000000009008', 'loc-sairan-quarry', 'Дымный уступ'),
    ('00000000-0000-0000-0000-000000009009', 'loc-teren-ruins', 'Старый дозор'),
    ('00000000-0000-0000-0000-00000000900a', 'loc-sairan-ruins', 'Пустой дозор'),
    ('00000000-0000-0000-0000-00000000900b', 'loc-teren-gates', 'Пепельная лощина'),
    ('00000000-0000-0000-0000-00000000900c', 'loc-sairan-gates', 'Стылый распадок'),
    ('00000000-0000-0000-0000-00000000900d', 'loc-borderland', 'Серая межа'),
]
ROADS = [
    ('loc-teren-city', 'loc-teren-suburb'),
    ('loc-teren-suburb', 'loc-teren-city'),
    ('loc-teren-suburb', 'loc-teren-forest'),
    ('loc-teren-forest', 'loc-teren-suburb'),
    ('loc-teren-forest', 'loc-teren-quarry'),
    ('loc-teren-quarry', 'loc-teren-forest'),
    ('loc-teren-quarry', 'loc-teren-ruins'),
    ('loc-teren-ruins', 'loc-teren-quarry'),
    ('loc-teren-ruins', 'loc-teren-gates'),
    ('loc-teren-gates', 'loc-teren-ruins'),
    ('loc-sairan-city', 'loc-sairan-suburb'),
    ('loc-sairan-suburb', 'loc-sairan-city'),
    ('loc-sairan-suburb', 'loc-sairan-forest'),
    ('loc-sairan-forest', 'loc-sairan-suburb'),
    ('loc-sairan-forest', 'loc-sairan-quarry'),
    ('loc-sairan-quarry', 'loc-sairan-forest'),
    ('loc-sairan-quarry', 'loc-sairan-ruins'),
    ('loc-sairan-ruins', 'loc-sairan-quarry'),
    ('loc-sairan-ruins', 'loc-sairan-gates'),
    ('loc-sairan-gates', 'loc-sairan-ruins'),
]


def upgrade():
    op.create_table(
        'locations',
        *base_columns(),
        sa.Column('code', sa.String(64), nullable=False),
        sa.Column('title', sa.String(128), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('image_url', sa.String(2048), nullable=True),
        schema='frontiers',
    )
    op.create_index('ix_frontiers_locations_code', 'locations', ['code'], unique=True, schema='frontiers')
    op.create_table(
        'location_transitions',
        *base_columns(),
        sa.Column('from_location_id', sa.Uuid(), sa.ForeignKey('frontiers.locations.id'), nullable=False),
        sa.Column('to_location_id', sa.Uuid(), sa.ForeignKey('frontiers.locations.id'), nullable=False),
        sa.Column('base_duration_seconds', sa.Integer(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('from_location_id', 'to_location_id', name='uq_location_transition_pair'),
        sa.CheckConstraint('from_location_id <> to_location_id', name='ck_transition_distinct_locations'),
        sa.CheckConstraint('base_duration_seconds > 0', name='ck_transition_positive_duration'),
        schema='frontiers',
    )
    for field in ('from_location_id', 'to_location_id'):
        op.create_index(
            f'ix_frontiers_location_transitions_{field}', 'location_transitions', [field], schema='frontiers'
        )
    locations = sa.table(
        'locations',
        sa.column('id', sa.Uuid()),
        sa.column('code', sa.String()),
        sa.column('title', sa.String()),
        schema='frontiers',
    )
    op.bulk_insert(locations, [dict(id=UUID(id), code=code, title=title) for id, code, title in LOCATIONS])
    ids = {code: UUID(id) for id, code, _ in LOCATIONS}
    roads = sa.table(
        'location_transitions',
        sa.column('id', sa.Uuid()),
        sa.column('from_location_id', sa.Uuid()),
        sa.column('to_location_id', sa.Uuid()),
        sa.column('base_duration_seconds', sa.Integer()),
        sa.column('is_enabled', sa.Boolean()),
        schema='frontiers',
    )
    op.bulk_insert(
        roads,
        [
            dict(id=uuid4(), from_location_id=ids[a], to_location_id=ids[b], base_duration_seconds=30, is_enabled=True)
            for a, b in ROADS
        ],
    )
    op.add_column('characters', sa.Column('location_id', sa.Uuid(), nullable=True), schema='frontiers')
    op.add_column(
        'characters', sa.Column('next_movement_at', sa.DateTime(timezone=True), nullable=True), schema='frontiers'
    )
    op.execute("UPDATE frontiers.characters SET location_id = '00000000-0000-0000-0000-000000009001'")
    op.alter_column('characters', 'location_id', nullable=False, schema='frontiers')
    op.create_foreign_key(
        'fk_characters_location',
        'characters',
        'locations',
        ['location_id'],
        ['id'],
        source_schema='frontiers',
        referent_schema='frontiers',
    )
    op.create_index('ix_frontiers_characters_location_id', 'characters', ['location_id'], schema='frontiers')
    for code, title, value, minimum, maximum in (
        ('movement_speed', 'Скорость перемещения', 100, 1, None),
        ('home_world', 'Родной мир (1 — Терен, 2 — Сайран)', 1, 1, 2),
    ):
        # Codes are unique. Preserve an existing definition if content already introduced it.
        op.execute(
            sa.text("""INSERT INTO frontiers.stat_definitions
            (id, code, title, kind, min_value, max_value)
            VALUES (:id, :code, :title, 'attribute', :minimum, :maximum)
            ON CONFLICT (code) DO NOTHING""").bindparams(
                id=uuid4(), code=code, title=title, minimum=minimum, maximum=maximum
            )
        )
        for table, owner_table, owner_key in (
            ('class_stats', 'character_classes', 'class_id'),
            ('character_stats', 'characters', 'character_id'),
        ):
            op.execute(
                sa.text(f"""INSERT INTO frontiers.{table} (id, {owner_key}, stat_definition_id, value)
                SELECT gen_random_uuid(), owner.id, definition.id, :value
                FROM frontiers.{owner_table} owner CROSS JOIN frontiers.stat_definitions definition
                WHERE definition.code = :code
                ON CONFLICT ({owner_key}, stat_definition_id) DO NOTHING""").bindparams(value=value, code=code)
            )


def downgrade():
    # Characteristics are content and may have acquired references since upgrade; retain them.
    op.drop_index('ix_frontiers_characters_location_id', table_name='characters', schema='frontiers')
    op.drop_constraint('fk_characters_location', 'characters', type_='foreignkey', schema='frontiers')
    op.drop_column('characters', 'next_movement_at', schema='frontiers')
    op.drop_column('characters', 'location_id', schema='frontiers')
    op.drop_table('location_transitions', schema='frontiers')
    op.drop_table('locations', schema='frontiers')

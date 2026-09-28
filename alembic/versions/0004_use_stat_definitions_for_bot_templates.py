"""Store bot values through shared stat definitions.

Revision ID: 0004
Revises: 0003
"""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'bot_template_stats',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('bot_template_id', sa.Uuid(), nullable=False),
        sa.Column('stat_definition_id', sa.Uuid(), nullable=False),
        sa.Column('value', sa.Numeric(18, 4), nullable=False),
        sa.ForeignKeyConstraint(['bot_template_id'], ['frontiers.bot_templates.id']),
        sa.ForeignKeyConstraint(['stat_definition_id'], ['frontiers.stat_definitions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bot_template_id', 'stat_definition_id', name='uq_bot_template_stat_pair'),
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_bot_template_stats_bot_template_id',
        'bot_template_stats',
        ['bot_template_id'],
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_bot_template_stats_stat_definition_id',
        'bot_template_stats',
        ['stat_definition_id'],
        schema='frontiers',
    )

    connection = op.get_bind()
    templates = (
        connection.execute(
            sa.text('SELECT id, max_health, attack, defense FROM frontiers.bot_templates'),
        )
        .mappings()
        .all()
    )
    if templates:
        definitions = {
            row['code']: row['id']
            for row in connection.execute(
                sa.text(
                    'SELECT id, code FROM frontiers.stat_definitions '
                    "WHERE code IN ('max_health', 'health', 'attack', 'defense')"
                ),
            ).mappings()
        }
        if {'max_health', 'health', 'attack', 'defense'} - definitions.keys():
            raise RuntimeError('Required stat definitions are missing')
        table = sa.table(
            'bot_template_stats',
            sa.column('id'),
            sa.column('bot_template_id'),
            sa.column('stat_definition_id'),
            sa.column('value'),
            schema='frontiers',
        )
        op.bulk_insert(
            table,
            [
                {
                    'id': uuid4(),
                    'bot_template_id': template['id'],
                    'stat_definition_id': definitions[code],
                    'value': template['max_health'] if code == 'health' else template[code],
                }
                for template in templates
                for code in ('max_health', 'health', 'attack', 'defense')
            ],
        )

    for code in ('max_health', 'attack', 'defense'):
        op.drop_column('bot_templates', code, schema='frontiers')


def downgrade() -> None:
    for code in ('max_health', 'attack', 'defense'):
        op.add_column('bot_templates', sa.Column(code, sa.Numeric(18, 4), nullable=True), schema='frontiers')
    op.get_bind().execute(
        sa.text(
            """
            UPDATE frontiers.bot_templates AS template
            SET max_health = COALESCE((
                    SELECT stat.value FROM frontiers.bot_template_stats AS stat
                    JOIN frontiers.stat_definitions AS definition ON definition.id = stat.stat_definition_id
                    WHERE stat.bot_template_id = template.id AND definition.code = 'max_health'
                      AND stat.is_archived = false
                ), 1),
                attack = COALESCE((
                    SELECT stat.value FROM frontiers.bot_template_stats AS stat
                    JOIN frontiers.stat_definitions AS definition ON definition.id = stat.stat_definition_id
                    WHERE stat.bot_template_id = template.id AND definition.code = 'attack'
                      AND stat.is_archived = false
                ), 0),
                defense = COALESCE((
                    SELECT stat.value FROM frontiers.bot_template_stats AS stat
                    JOIN frontiers.stat_definitions AS definition ON definition.id = stat.stat_definition_id
                    WHERE stat.bot_template_id = template.id AND definition.code = 'defense'
                      AND stat.is_archived = false
                ), 0)
            """
        ),
    )
    for code in ('max_health', 'attack', 'defense'):
        op.alter_column('bot_templates', code, nullable=False, schema='frontiers')
    op.drop_index(
        'ix_frontiers_bot_template_stats_stat_definition_id',
        table_name='bot_template_stats',
        schema='frontiers',
    )
    op.drop_index(
        'ix_frontiers_bot_template_stats_bot_template_id',
        table_name='bot_template_stats',
        schema='frontiers',
    )
    op.drop_table('bot_template_stats', schema='frontiers')

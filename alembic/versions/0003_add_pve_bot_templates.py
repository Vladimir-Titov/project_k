"""Add PvE bot template tables.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa

from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'bot_templates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('max_health', sa.Numeric(18, 4), nullable=False),
        sa.Column('attack', sa.Numeric(18, 4), nullable=False),
        sa.Column('defense', sa.Numeric(18, 4), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='frontiers',
    )
    op.create_index('ix_frontiers_bot_templates_code', 'bot_templates', ['code'], unique=True, schema='frontiers')
    op.create_table(
        'bot_template_actions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('bot_template_id', sa.Uuid(), nullable=False),
        sa.Column('action_definition_id', sa.Uuid(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['bot_template_id'], ['frontiers.bot_templates.id']),
        sa.ForeignKeyConstraint(['action_definition_id'], ['frontiers.action_definitions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bot_template_id', 'action_definition_id', name='uq_bot_template_action_pair'),
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_bot_template_actions_bot_template_id',
        'bot_template_actions',
        ['bot_template_id'],
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_bot_template_actions_action_definition_id',
        'bot_template_actions',
        ['action_definition_id'],
        schema='frontiers',
    )
    op.add_column('fight_participants', sa.Column('bot_template_id', sa.Uuid(), nullable=True), schema='frontiers')
    op.create_foreign_key(
        'fk_fight_participants_bot_template',
        'fight_participants',
        'bot_templates',
        ['bot_template_id'],
        ['id'],
        source_schema='frontiers',
        referent_schema='frontiers',
    )


def downgrade() -> None:
    op.drop_constraint('fk_fight_participants_bot_template', 'fight_participants', schema='frontiers')
    op.drop_column('fight_participants', 'bot_template_id', schema='frontiers')
    op.drop_index(
        'ix_frontiers_bot_template_actions_action_definition_id',
        table_name='bot_template_actions',
        schema='frontiers',
    )
    op.drop_index(
        'ix_frontiers_bot_template_actions_bot_template_id',
        table_name='bot_template_actions',
        schema='frontiers',
    )
    op.drop_table('bot_template_actions', schema='frontiers')
    op.drop_index('ix_frontiers_bot_templates_code', table_name='bot_templates', schema='frontiers')
    op.drop_table('bot_templates', schema='frontiers')

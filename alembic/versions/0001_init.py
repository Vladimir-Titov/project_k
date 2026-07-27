"""init

Revision ID: 0001
Revises: 
Create Date: 2026-07-27 17:28:50.569170

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "frontiers"')
    op.create_table('account',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('login', sa.String(), nullable=False),
    sa.Column('password', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='frontiers'
    )
    op.create_index(op.f('ix_frontiers_account_login'), 'account', ['login'], unique=False, schema='frontiers')
    op.create_table('actions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('type', sa.Enum('started', 'finished', 'interrupted', 'in_progress', 'canceled', name='actions_type', native_enum=False), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='frontiers'
    )
    op.create_table('characteristics',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='frontiers'
    )
    op.create_table('characters',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('account_id', sa.String(), nullable=False),
    sa.Column('nickname', sa.String(), nullable=False),
    sa.Column('character_class', sa.Enum('adventurer', name='character_class', native_enum=False), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='frontiers'
    )
    op.create_index(op.f('ix_frontiers_characters_account_id'), 'characters', ['account_id'], unique=False, schema='frontiers')
    op.create_index(op.f('ix_frontiers_characters_nickname'), 'characters', ['nickname'], unique=True, schema='frontiers')
    op.create_table('fights',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('status', sa.Enum('started', 'finished', 'interrupted', 'in_progress', 'canceled', name='fight_status', native_enum=False), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('winner_side', sa.Enum('team_a', 'team_b', name='fight_side', native_enum=False), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='frontiers'
    )
    op.create_table('mobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='frontiers'
    )
    op.create_index(op.f('ix_frontiers_mobs_name'), 'mobs', ['name'], unique=False, schema='frontiers')
    op.create_table('fight_participants',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('fight_id', sa.Uuid(), nullable=False),
    sa.Column('character_id', sa.Uuid(), nullable=True),
    sa.Column('mob_id', sa.Uuid(), nullable=True),
    sa.Column('side', sa.Enum('team_a', 'team_b', name='fight_side', native_enum=False), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['frontiers.characters.id'], ),
    sa.ForeignKeyConstraint(['fight_id'], ['frontiers.fights.id'], ),
    sa.ForeignKeyConstraint(['mob_id'], ['frontiers.mobs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='frontiers'
    )
    op.create_index(op.f('ix_frontiers_fight_participants_fight_id'), 'fight_participants', ['fight_id'], unique=False, schema='frontiers')
    op.create_table('fight_actions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('fight_id', sa.Uuid(), nullable=False),
    sa.Column('action_id', sa.Uuid(), nullable=False),
    sa.Column('initiator_participant_id', sa.Uuid(), nullable=False),
    sa.Column('target_participant_id', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['action_id'], ['frontiers.actions.id'], ),
    sa.ForeignKeyConstraint(['fight_id'], ['frontiers.fights.id'], ),
    sa.ForeignKeyConstraint(['initiator_participant_id'], ['frontiers.fight_participants.id'], ),
    sa.ForeignKeyConstraint(['target_participant_id'], ['frontiers.fight_participants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='frontiers'
    )
    op.create_index(op.f('ix_frontiers_fight_actions_fight_id'), 'fight_actions', ['fight_id'], unique=False, schema='frontiers')


def downgrade() -> None:
    op.drop_index(op.f('ix_frontiers_fight_actions_fight_id'), table_name='fight_actions', schema='frontiers')
    op.drop_table('fight_actions', schema='frontiers')
    op.drop_index(op.f('ix_frontiers_fight_participants_fight_id'), table_name='fight_participants', schema='frontiers')
    op.drop_table('fight_participants', schema='frontiers')
    op.drop_index(op.f('ix_frontiers_mobs_name'), table_name='mobs', schema='frontiers')
    op.drop_table('mobs', schema='frontiers')
    op.drop_table('fights', schema='frontiers')
    op.drop_index(op.f('ix_frontiers_characters_nickname'), table_name='characters', schema='frontiers')
    op.drop_index(op.f('ix_frontiers_characters_account_id'), table_name='characters', schema='frontiers')
    op.drop_table('characters', schema='frontiers')
    op.drop_table('characteristics', schema='frontiers')
    op.drop_table('actions', schema='frontiers')
    op.drop_index(op.f('ix_frontiers_account_login'), table_name='account', schema='frontiers')
    op.drop_table('account', schema='frontiers')

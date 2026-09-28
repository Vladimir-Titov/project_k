"""Add optional image URLs to action and effect definitions.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('action_definitions', sa.Column('image_url', sa.Text(), nullable=True), schema='frontiers')
    op.add_column('effect_definitions', sa.Column('image_url', sa.Text(), nullable=True), schema='frontiers')


def downgrade() -> None:
    op.drop_column('effect_definitions', 'image_url', schema='frontiers')
    op.drop_column('action_definitions', 'image_url', schema='frontiers')

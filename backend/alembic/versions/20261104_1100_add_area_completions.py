"""add_area_completions

Revision ID: 3d8e5a1c7b20
Revises: fb27e8ae9722
Create Date: 2026-11-04 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3d8e5a1c7b20'
down_revision = 'fb27e8ae9722'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One row per "Finish Exploring" click on an area's room-selection screen
    op.create_table(
        'area_completions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('area', sa.String(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_area_completions_session_id', 'area_completions', ['session_id'])
    op.create_index('ix_area_completions_user_id', 'area_completions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_area_completions_user_id', table_name='area_completions')
    op.drop_index('ix_area_completions_session_id', table_name='area_completions')
    op.drop_table('area_completions')

"""add_progress_resets

"Restart" button on the map: one row per click. Progress, finished areas and
chats to resume only count what happened after the latest reset; earlier rows
are kept.

Revision ID: 9d4b6f1a2c38
Revises: 8c1f3a6d9e27
Create Date: 2026-11-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d4b6f1a2c38'
down_revision = '8c1f3a6d9e27'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'progress_resets',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('reset_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_progress_resets_session_id', 'progress_resets', ['session_id'])
    op.create_index('ix_progress_resets_user_id', 'progress_resets', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_progress_resets_user_id', table_name='progress_resets')
    op.drop_index('ix_progress_resets_session_id', table_name='progress_resets')
    op.drop_table('progress_resets')

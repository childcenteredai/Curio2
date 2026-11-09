"""add_direct_instruction

Direct-instruction version: area completions are kept per app version, and each
step through Nova's explanation is logged.

Revision ID: 5b7c9d2e4f61
Revises: 3d8e5a1c7b20
Create Date: 2026-11-04 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5b7c9d2e4f61'
down_revision = '3d8e5a1c7b20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows all come from the question-asking version
    op.add_column(
        'area_completions',
        sa.Column('version', sa.String(), nullable=False, server_default='qa'),
    )

    op.create_table(
        'explanation_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('area', sa.String(), nullable=False),
        sa.Column('phenomenon', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('step', sa.Integer(), nullable=True),
        sa.Column('concept', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_explanation_events_session_id', 'explanation_events', ['session_id'])
    op.create_index('ix_explanation_events_user_id', 'explanation_events', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_explanation_events_user_id', table_name='explanation_events')
    op.drop_index('ix_explanation_events_session_id', table_name='explanation_events')
    op.drop_table('explanation_events')
    op.drop_column('area_completions', 'version')

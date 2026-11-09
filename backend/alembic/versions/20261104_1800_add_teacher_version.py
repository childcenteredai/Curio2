"""add_teacher_version

Teacher version (/teacher): conversations are tagged with the app version they
happened in, and a teacher-sent message keeps the raw speech-to-text result next
to the edited text that was sent.

Revision ID: 8c1f3a6d9e27
Revises: 5b7c9d2e4f61
Create Date: 2026-11-04 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c1f3a6d9e27'
down_revision = '5b7c9d2e4f61'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing conversations all come from the question-asking version
    op.add_column(
        'conversations',
        sa.Column('version', sa.String(), nullable=False, server_default='qa'),
    )
    op.add_column('messages', sa.Column('transcript', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'transcript')
    op.drop_column('conversations', 'version')

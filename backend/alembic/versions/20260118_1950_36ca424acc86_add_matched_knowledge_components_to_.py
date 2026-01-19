"""add_matched_knowledge_components_to_messages

Revision ID: 36ca424acc86
Revises: a1124e2adddc
Create Date: 2026-01-18 19:50:54.953069

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '36ca424acc86'
down_revision = 'a1124e2adddc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add matched_knowledge_components column to messages table
    op.add_column('messages', sa.Column('matched_knowledge_components', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove matched_knowledge_components column from messages table
    op.drop_column('messages', 'matched_knowledge_components')

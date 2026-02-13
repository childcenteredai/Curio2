"""add_user_fields_to_conversations

Revision ID: 7b9f2c1d3e45
Revises: 36ca424acc86
Create Date: 2026-01-28 08:08:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7b9f2c1d3e45"
down_revision = "36ca424acc86"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add user information columns to conversations table."""
    op.add_column("conversations", sa.Column("user_id", sa.String(), nullable=True))
    op.add_column("conversations", sa.Column("user_email", sa.String(), nullable=True))
    op.add_column("conversations", sa.Column("username", sa.String(), nullable=True))
    op.add_column("conversations", sa.Column("user_groups", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove user information columns from conversations table."""
    op.drop_column("conversations", "user_groups")
    op.drop_column("conversations", "username")
    op.drop_column("conversations", "user_email")
    op.drop_column("conversations", "user_id")




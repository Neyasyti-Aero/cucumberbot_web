"""map templates: map_type column, optional file_key

Revision ID: 002
Revises: 001
Create Date: 2025-02-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("maps", sa.Column("map_type", sa.String(20), nullable=False, server_default="geo"))
    op.alter_column("maps", "file_key", existing_type=sa.String(512), nullable=True)


def downgrade() -> None:
    op.alter_column("maps", "file_key", existing_type=sa.String(512), nullable=False)
    op.drop_column("maps", "map_type")

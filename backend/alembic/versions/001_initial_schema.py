"""initial schema + default admin

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00
"""

import os
import uuid
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from passlib.context import CryptContext

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "maps",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("file_key", sa.String(512), nullable=False),
        sa.Column("geojson_key", sa.String(512), nullable=True),
        sa.Column("thumbnail_key", sa.String(512), nullable=True),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("width_meters", sa.Float, nullable=True),
        sa.Column("height_meters", sa.Float, nullable=True),
        sa.Column("resolution", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "qr_codes",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("map_id", sa.UUID(as_uuid=True), sa.ForeignKey("maps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("x", sa.Float, nullable=False),
        sa.Column("y", sa.Float, nullable=False),
        sa.Column("theta", sa.Float, nullable=False, server_default="0"),
        sa.Column("image_key", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "command_logs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("command_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.Text, server_default="{}"),
        sa.Column("acknowledged", sa.Boolean, server_default="false"),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "terminal_logs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("command", sa.Text, nullable=False),
        sa.Column("output", sa.Text, server_default=""),
        sa.Column("exit_code", sa.String(10), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    admin_email = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@cucumberbot.io")
    admin_password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "Admin1234!")

    op.execute(
        sa.text(
            "INSERT INTO users (id, email, hashed_password, role, is_active) "
            "VALUES (:id, :email, :pwd, 'admin', true)"
        ).bindparams(
            id=str(uuid.uuid4()),
            email=admin_email,
            pwd=_pwd_ctx.hash(admin_password),
        )
    )


def downgrade() -> None:
    op.drop_table("terminal_logs")
    op.drop_table("command_logs")
    op.drop_table("qr_codes")
    op.drop_table("maps")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")

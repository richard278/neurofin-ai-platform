"""create refresh sessions and refresh tokens tables

Revision ID: 20260829a002
Revises: 20260829a001
Create Date: 2026-08-29 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260829a002"
down_revision: str | None = "20260829a001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_sessions"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_refresh_sessions_user_id_users",
        ),
        sa.CheckConstraint(
            "absolute_expires_at > created_at",
            name="ck_refresh_sessions_absolute_expiry",
        ),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_token_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["refresh_sessions.id"],
            name="fk_refresh_tokens_session_id_refresh_sessions",
        ),
        sa.ForeignKeyConstraint(
            ["parent_token_id"],
            ["refresh_tokens.id"],
            name="fk_refresh_tokens_parent_token_id_refresh_tokens",
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        sa.UniqueConstraint("parent_token_id", name="uq_refresh_tokens_parent_token_id"),
        sa.CheckConstraint(
            "octet_length(token_hash) = 32",
            name="ck_refresh_tokens_hash_length",
        ),
        sa.CheckConstraint(
            "expires_at > issued_at",
            name="ck_refresh_tokens_expiry",
        ),
    )


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("refresh_sessions")

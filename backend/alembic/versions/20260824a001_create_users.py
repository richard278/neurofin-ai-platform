"""create users

Revision ID: 20260824a001
Revises: 116464527395
Create Date: 2026-08-24 17:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260824a001"
down_revision: str | Sequence[str] | None = "116464527395"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "email = lower(btrim(email))",
            name="ck_users_email_canonical",
        ),
        sa.CheckConstraint(
            "role IN ('ANALYST', 'ADMIN')",
            name="ck_users_role",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )


def downgrade() -> None:
    op.drop_table("users")

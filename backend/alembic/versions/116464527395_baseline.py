"""baseline

Revision ID: 116464527395
Revises:
Create Date: 2026-08-20 13:28:08.703742

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '116464527395'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""

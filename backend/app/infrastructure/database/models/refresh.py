from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    LargeBinary,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class RefreshSessionModel(Base):
    __tablename__ = "refresh_sessions"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_refresh_sessions"),
        ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_refresh_sessions_user_id_users",
        ),
        CheckConstraint(
            "absolute_expires_at > created_at",
            name="ck_refresh_sessions_absolute_expiry",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        PrimaryKeyConstraint(
            "id",
            name="pk_refresh_tokens",
        ),
        ForeignKeyConstraint(
            ["session_id"],
            ["refresh_sessions.id"],
            name="fk_refresh_tokens_session_id_refresh_sessions",
        ),
        ForeignKeyConstraint(
            ["parent_token_id"],
            ["refresh_tokens.id"],
            name="fk_refresh_tokens_parent_token_id_refresh_tokens",
        ),
        UniqueConstraint(
            "token_hash",
            name="uq_refresh_tokens_token_hash",
        ),
        UniqueConstraint(
            "parent_token_id",
            name="uq_refresh_tokens_parent_token_id",
        ),
        CheckConstraint(
            "octet_length(token_hash) = 32",
            name="ck_refresh_tokens_hash_length",
        ),
        CheckConstraint(
            "expires_at > issued_at",
            name="ck_refresh_tokens_expiry",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    parent_token_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
    token_hash: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
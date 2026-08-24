from uuid import UUID

from sqlalchemy import CheckConstraint, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_users"),
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint(
            "email = lower(btrim(email))", name="ck_users_email_canonical"
        ),
        CheckConstraint(
            "role IN ('ANALYST', 'ADMIN')", name="ck_users_role"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)

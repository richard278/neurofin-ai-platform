from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, PrimaryKeyConstraint, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class UserCredentialModel(Base):
    __tablename__ = "user_credentials"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", name="pk_user_credentials"),
        ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_credentials_user_id_users",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

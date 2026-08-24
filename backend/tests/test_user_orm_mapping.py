from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.domain.entities.user import InvalidUserEmailError, User, UserRole
from app.infrastructure.database.base import Base
from app.infrastructure.database.mappers.user_mapper import user_to_domain, user_to_model
from app.infrastructure.database.models.user import UserModel


def test_user_model_metadata_matches_contract() -> None:
    table = UserModel.__table__

    assert table.metadata is Base.metadata
    assert table.name == "users"
    assert set(table.columns.keys()) == {"id", "email", "role"}

    id_column = table.c.id
    email_column = table.c.email
    role_column = table.c.role

    assert isinstance(id_column.type, PGUUID)
    assert id_column.nullable is False
    assert id_column.server_default is None

    assert isinstance(email_column.type, String)
    assert email_column.type.length == 254
    assert email_column.nullable is False

    assert isinstance(role_column.type, String)
    assert role_column.type.length == 16
    assert role_column.nullable is False
    assert role_column.server_default is None

    constraints = {constraint.name: constraint for constraint in table.constraints}
    assert isinstance(constraints["pk_users"], PrimaryKeyConstraint)
    assert isinstance(constraints["uq_users_email"], UniqueConstraint)
    assert isinstance(constraints["ck_users_email_canonical"], CheckConstraint)
    assert isinstance(constraints["ck_users_role"], CheckConstraint)


@pytest.mark.parametrize("role", [UserRole.ANALYST, UserRole.ADMIN])
def test_mapper_round_trip_preserves_identity(role: UserRole) -> None:
    user = User(id=uuid4(), email="user@example.com", role=role)

    model = user_to_model(user)
    restored = user_to_domain(model)

    assert model.id == user.id
    assert model.email == user.email
    assert model.role == role.value
    assert restored == user


def test_user_to_domain_rejects_unknown_persisted_role() -> None:
    model = UserModel(id=uuid4(), email="user@example.com", role="SUPERADMIN")

    with pytest.raises(ValueError):
        user_to_domain(model)


def test_user_to_domain_rejects_noncanonical_persisted_email() -> None:
    model = UserModel(id=uuid4(), email="User@Example.COM", role="ANALYST")

    with pytest.raises(InvalidUserEmailError):
        user_to_domain(model)

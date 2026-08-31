from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest

from app.domain.entities.user import (
    InvalidUserEmailError,
    User,
    UserRole,
    canonicalize_user_email,
)
from app.domain.repositories.user_repository import (
    UserAlreadyExistsError,
    UserRepository,
    UserRepositoryError,
)


def test_canonicalize_user_email_matches_user_create() -> None:
    raw = "  Richard.Milian+lab@Example.COM  "
    canonical = canonicalize_user_email(raw)
    assert canonical == User.create(raw, UserRole.ANALYST).email


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Richard@Example.COM", "richard@example.com"),
        ("  Richard.Milian+lab@Example.COM  ", "richard.milian+lab@example.com"),
        ("r_milian@sub.example.com", "r_milian@sub.example.com"),
    ],
)
def test_user_create_canonicalizes_valid_email(raw: str, expected: str) -> None:
    user = User.create(raw, UserRole.ANALYST)

    assert isinstance(user.id, UUID)
    assert user.email == expected
    assert user.role is UserRole.ANALYST


@pytest.mark.parametrize(
    "email",
    [
        "user@localhost",
        "user@@example.com",
        ".user@example.com",
        "user.@example.com",
        "user..name@example.com",
        "user@-example.com",
        "user@example-.com",
        "user@example..com",
        "üser@example.com",
        "\"user name\"@example.com",
        "user@[127.0.0.1]",
        "user name@example.com",
        "user\n@example.com",
        f"{'a' * 65}@example.com",
        f"{'a' * 64}@{'b' * 63}.{'c' * 63}.{'d' * 61}.com",
    ],
)
def test_user_create_rejects_invalid_email(email: str) -> None:
    with pytest.raises(InvalidUserEmailError):
        User.create(email, UserRole.ANALYST)


def test_user_constructor_rejects_noncanonical_persisted_email() -> None:
    with pytest.raises(InvalidUserEmailError):
        User(id=uuid4(), email="Richard@Example.COM", role=UserRole.ANALYST)


def test_user_constructor_rejects_wrong_id_type() -> None:
    with pytest.raises(TypeError, match="id must be UUID"):
        User(id="not-a-uuid", email="user@example.com", role=UserRole.ANALYST)  # type: ignore[arg-type]


def test_user_constructor_rejects_wrong_role_type() -> None:
    with pytest.raises(TypeError, match="role must be UserRole"):
        User(id=uuid4(), email="user@example.com", role="ADMIN")  # type: ignore[arg-type]


def test_user_is_frozen() -> None:
    user = User.create("user@example.com", UserRole.ANALYST)

    with pytest.raises(FrozenInstanceError):
        user.email = "other@example.com"  # type: ignore[misc]


def test_user_role_values_are_exact() -> None:
    assert UserRole.ANALYST.value == "ANALYST"
    assert UserRole.ADMIN.value == "ADMIN"

    with pytest.raises(ValueError):
        UserRole("SUPERADMIN")


def test_repository_errors_are_persistence_agnostic() -> None:
    assert issubclass(UserAlreadyExistsError, UserRepositoryError)
    assert UserRepository.__module__ == "app.domain.repositories.user_repository"

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User, UserRole
from app.domain.repositories.user_repository import (
    UserAlreadyExistsError,
    UserRepositoryError,
)
from app.infrastructure.database.models.user import UserModel
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)


class StructuredDriverError(Exception):
    def __init__(self, sqlstate: str, constraint_name: str) -> None:
        super().__init__("structured driver error")
        self.sqlstate = sqlstate
        self.constraint_name = constraint_name


def _session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_add_uses_add_and_flush_without_commit_or_rollback() -> None:
    session = _session()
    repository = SQLAlchemyUserRepository(session)
    user = User.create("user@example.com", UserRole.ANALYST)

    await repository.add(user)

    session.add.assert_called_once()
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    session.close.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("constraint_name", ["uq_users_email", "pk_users"])
async def test_identity_unique_constraints_translate_to_user_already_exists(
    constraint_name: str,
) -> None:
    session = _session()
    session.flush.side_effect = IntegrityError(
        "INSERT INTO users ...",
        {},
        StructuredDriverError("23505", constraint_name),
    )
    repository = SQLAlchemyUserRepository(session)
    user = User.create("user@example.com", UserRole.ANALYST)

    with pytest.raises(UserAlreadyExistsError) as exc_info:
        await repository.add(user)

    assert isinstance(exc_info.value.__cause__, IntegrityError)
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_integrity_constraint_is_generic_repository_error() -> None:
    session = _session()
    session.flush.side_effect = IntegrityError(
        "INSERT INTO users ...",
        {},
        StructuredDriverError("23514", "ck_users_role"),
    )
    repository = SQLAlchemyUserRepository(session)
    user = User.create("user@example.com", UserRole.ANALYST)

    with pytest.raises(UserRepositoryError) as exc_info:
        await repository.add(user)

    assert type(exc_info.value) is UserRepositoryError
    assert isinstance(exc_info.value.__cause__, IntegrityError)


@pytest.mark.asyncio
async def test_get_by_id_maps_model_to_domain() -> None:
    session = _session()
    user_id = uuid4()
    session.get.return_value = UserModel(
        id=user_id,
        email="user@example.com",
        role="ANALYST",
    )
    repository = SQLAlchemyUserRepository(session)

    user = await repository.get_by_id(user_id)

    assert user == User(id=user_id, email="user@example.com", role=UserRole.ANALYST)


@pytest.mark.asyncio
async def test_get_by_id_missing_returns_none() -> None:
    session = _session()
    session.get.return_value = None
    repository = SQLAlchemyUserRepository(session)

    assert await repository.get_by_id(uuid4()) is None


@pytest.mark.asyncio
async def test_get_by_email_executes_exact_query_and_maps_result() -> None:
    session = _session()
    result = MagicMock()
    result.scalar_one_or_none.return_value = UserModel(
        id=uuid4(),
        email="user@example.com",
        role="ADMIN",
    )
    session.execute.return_value = result
    repository = SQLAlchemyUserRepository(session)

    user = await repository.get_by_email("user@example.com")

    session.execute.assert_awaited_once()
    assert user is not None
    assert user.email == "user@example.com"
    assert user.role is UserRole.ADMIN


@pytest.mark.asyncio
async def test_sqlalchemy_query_failure_translates_to_repository_error() -> None:
    session = _session()
    session.get.side_effect = SQLAlchemyError("database unavailable")
    repository = SQLAlchemyUserRepository(session)

    with pytest.raises(UserRepositoryError) as exc_info:
        await repository.get_by_id(uuid4())

    assert isinstance(exc_info.value.__cause__, SQLAlchemyError)

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.security.credentials import (
    CredentialAlreadyExistsError,
    CredentialRepositoryError,
    PasswordCredential,
)
from app.infrastructure.database.mappers.credential_mapper import (
    credential_to_model,
    model_to_credential,
)
from app.infrastructure.database.models.user_credential import UserCredentialModel
from app.infrastructure.repositories.sqlalchemy_credential_repository import (
    SQLAlchemyCredentialRepository,
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


def test_user_credential_model_structure() -> None:
    table = UserCredentialModel.__table__
    assert table.name == "user_credentials"
    column_names = {c.name for c in table.columns}
    assert column_names == {"user_id", "password_hash"}

    user_id_col = table.columns["user_id"]
    assert user_id_col.primary_key is True
    assert user_id_col.nullable is False

    password_hash_col = table.columns["password_hash"]
    assert password_hash_col.primary_key is False
    assert password_hash_col.nullable is False

    pks = [pk.name for pk in table.primary_key]
    assert pks == ["user_id"]
    assert table.primary_key.name == "pk_user_credentials"

    fks = list(table.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.constraint.name == "fk_user_credentials_user_id_users"
    assert fk.target_fullname == "users.id"


def test_credential_mapper_round_trip() -> None:
    user_id = uuid4()
    phc = "$argon2id$v=19$m=65536,t=3,p=4$some_salt$some_hash"
    credential = PasswordCredential(user_id=user_id, password_hash=phc)

    model = credential_to_model(credential)
    assert isinstance(model, UserCredentialModel)
    assert model.user_id == user_id
    assert model.password_hash == phc

    restored = model_to_credential(model)
    assert restored == credential


@pytest.mark.asyncio
async def test_add_uses_add_and_flush_without_commit_or_rollback() -> None:
    session = _session()
    repository = SQLAlchemyCredentialRepository(session)
    user_id = uuid4()
    credential = PasswordCredential(
        user_id=user_id,
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$salt$hash",
    )

    await repository.add(credential)

    session.add.assert_called_once()
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    session.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_duplicate_pk_raises_credential_already_exists_error() -> None:
    session = _session()
    session.flush.side_effect = IntegrityError(
        "INSERT INTO user_credentials ...",
        {},
        StructuredDriverError("23505", "pk_user_credentials"),
    )
    repository = SQLAlchemyCredentialRepository(session)
    credential = PasswordCredential(
        user_id=uuid4(),
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$salt$hash",
    )

    with pytest.raises(CredentialAlreadyExistsError) as exc_info:
        await repository.add(credential)

    assert isinstance(exc_info.value.__cause__, IntegrityError)
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_other_integrity_error_raises_generic_repository_error() -> None:
    session = _session()
    session.flush.side_effect = IntegrityError(
        "INSERT INTO user_credentials ...",
        {},
        StructuredDriverError("23503", "fk_user_credentials_user_id_users"),
    )
    repository = SQLAlchemyCredentialRepository(session)
    credential = PasswordCredential(
        user_id=uuid4(),
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$salt$hash",
    )

    with pytest.raises(CredentialRepositoryError) as exc_info:
        await repository.add(credential)

    assert type(exc_info.value) is CredentialRepositoryError
    assert isinstance(exc_info.value.__cause__, IntegrityError)


@pytest.mark.asyncio
async def test_add_generic_sqlalchemy_error_raises_repository_error() -> None:
    session = _session()
    session.flush.side_effect = SQLAlchemyError("database error")
    repository = SQLAlchemyCredentialRepository(session)
    credential = PasswordCredential(
        user_id=uuid4(),
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$salt$hash",
    )

    with pytest.raises(CredentialRepositoryError) as exc_info:
        await repository.add(credential)

    assert isinstance(exc_info.value.__cause__, SQLAlchemyError)


@pytest.mark.asyncio
async def test_get_by_user_id_returns_mapped_credential() -> None:
    session = _session()
    user_id = uuid4()
    phc = "$argon2id$v=19$m=65536,t=3,p=4$salt$hash"
    session.get.return_value = UserCredentialModel(
        user_id=user_id,
        password_hash=phc,
    )
    repository = SQLAlchemyCredentialRepository(session)

    credential = await repository.get_by_user_id(user_id)

    assert credential == PasswordCredential(user_id=user_id, password_hash=phc)
    session.get.assert_awaited_once_with(UserCredentialModel, user_id)


@pytest.mark.asyncio
async def test_get_by_user_id_returns_none_when_missing() -> None:
    session = _session()
    session.get.return_value = None
    repository = SQLAlchemyCredentialRepository(session)

    credential = await repository.get_by_user_id(uuid4())

    assert credential is None


@pytest.mark.asyncio
async def test_get_by_user_id_sqlalchemy_failure_raises_repository_error() -> None:
    session = _session()
    session.get.side_effect = SQLAlchemyError("connection failure")
    repository = SQLAlchemyCredentialRepository(session)

    with pytest.raises(CredentialRepositoryError) as exc_info:
        await repository.get_by_user_id(uuid4())

    assert isinstance(exc_info.value.__cause__, SQLAlchemyError)


@pytest.mark.asyncio
async def test_replace_hash_returns_true_when_updated() -> None:
    session = _session()
    result_mock = MagicMock()
    result_mock.rowcount = 1
    session.execute.return_value = result_mock
    repository = SQLAlchemyCredentialRepository(session)

    user_id = uuid4()
    old_hash = "$argon2id$v=19$m=65536,t=3,p=4$salt$old"
    new_hash = "$argon2id$v=19$m=65536,t=3,p=4$salt$new"

    success = await repository.replace_hash(
        user_id=user_id,
        expected_hash=old_hash,
        replacement_hash=new_hash,
    )

    assert success is True
    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_replace_hash_returns_false_when_expected_hash_does_not_match() -> None:
    session = _session()
    result_mock = MagicMock()
    result_mock.rowcount = 0
    session.execute.return_value = result_mock
    repository = SQLAlchemyCredentialRepository(session)

    user_id = uuid4()
    old_hash = "$argon2id$v=19$m=65536,t=3,p=4$salt$old"
    new_hash = "$argon2id$v=19$m=65536,t=3,p=4$salt$new"

    success = await repository.replace_hash(
        user_id=user_id,
        expected_hash=old_hash,
        replacement_hash=new_hash,
    )

    assert success is False


@pytest.mark.asyncio
async def test_replace_hash_sqlalchemy_failure_raises_repository_error() -> None:
    session = _session()
    session.execute.side_effect = SQLAlchemyError("update error")
    repository = SQLAlchemyCredentialRepository(session)

    with pytest.raises(CredentialRepositoryError) as exc_info:
        await repository.replace_hash(
            user_id=uuid4(),
            expected_hash="old",
            replacement_hash="new",
        )

    assert isinstance(exc_info.value.__cause__, SQLAlchemyError)

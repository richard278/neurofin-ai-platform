from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    LargeBinary,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.security.refresh import (
    RefreshRepositoryError,
    RefreshSessionRecord,
    RefreshTokenRecord,
)
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.refresh import (
    RefreshSessionModel,
    RefreshTokenModel,
)


def _load_sqlalchemy_refresh_repository() -> type[Any]:
    try:
        from app.infrastructure.repositories.sqlalchemy_refresh_repository import (
            SQLAlchemyRefreshRepository,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(
            f"sqlalchemy refresh repository is not implemented: {exc}"
        )

    return SQLAlchemyRefreshRepository


def _load_session_mappers() -> tuple[Any, Any]:
    try:
        from app.infrastructure.database.mappers.refresh_mapper import (
            model_to_session,
            session_to_model,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"refresh session mapper is not implemented: {exc}")

    return session_to_model, model_to_session


def _load_token_mappers() -> tuple[Any, Any]:
    try:
        from app.infrastructure.database.mappers.refresh_mapper import (
            model_to_token,
            token_to_model,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"refresh token mapper is not implemented: {exc}")

    return token_to_model, model_to_token


def _load_refresh_repository_error() -> type[Exception]:
    try:
        from app.application.security.refresh import RefreshRepositoryError
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(
            f"refresh repository error contract is not implemented: {exc}"
        )

    return RefreshRepositoryError


def _load_refresh_session_model() -> type[Any]:
    try:
        from app.infrastructure.database.models.refresh import RefreshSessionModel
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"refresh session ORM model is not implemented: {exc}")

    return RefreshSessionModel


def _load_refresh_token_model() -> type[Any]:
    try:
        from app.infrastructure.database.models.refresh import RefreshTokenModel
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"refresh token ORM model is not implemented: {exc}")

    return RefreshTokenModel


def _load_registered_refresh_models() -> tuple[
    type[Any],
    type[Any],
    list[str],
]:
    try:
        from app.infrastructure.database.models import (
            RefreshSessionModel,
            RefreshTokenModel,
            __all__,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"refresh ORM models are not registered: {exc}")

    return RefreshSessionModel, RefreshTokenModel, __all__


def test_refresh_session_model_matches_contract() -> None:
    refresh_session_model = _load_refresh_session_model()
    table = refresh_session_model.__table__

    assert table.metadata is Base.metadata
    assert table.name == "refresh_sessions"
    assert set(table.columns.keys()) == {
        "id",
        "user_id",
        "created_at",
        "absolute_expires_at",
        "revoked_at",
    }

    id_column = table.c.id
    user_id_column = table.c.user_id
    created_at_column = table.c.created_at
    absolute_expires_at_column = table.c.absolute_expires_at
    revoked_at_column = table.c.revoked_at

    assert isinstance(id_column.type, PGUUID)
    assert id_column.primary_key is True
    assert id_column.nullable is False

    assert isinstance(user_id_column.type, PGUUID)
    assert user_id_column.nullable is False

    for timestamp_column in (
        created_at_column,
        absolute_expires_at_column,
        revoked_at_column,
    ):
        assert isinstance(timestamp_column.type, DateTime)
        assert timestamp_column.type.timezone is True

    assert created_at_column.nullable is False
    assert absolute_expires_at_column.nullable is False
    assert revoked_at_column.nullable is True

    constraints = {
        constraint.name: constraint
        for constraint in table.constraints
    }

    assert set(constraints) == {
        "pk_refresh_sessions",
        "fk_refresh_sessions_user_id_users",
        "ck_refresh_sessions_absolute_expiry",
    }
    assert isinstance(
        constraints["pk_refresh_sessions"],
        PrimaryKeyConstraint,
    )
    assert isinstance(
        constraints["ck_refresh_sessions_absolute_expiry"],
        CheckConstraint,
    )

    foreign_keys = list(table.foreign_keys)
    assert len(foreign_keys) == 1

    user_foreign_key = foreign_keys[0]
    assert user_foreign_key.parent.name == "user_id"
    assert user_foreign_key.target_fullname == "users.id"
    assert (
        user_foreign_key.constraint.name
        == "fk_refresh_sessions_user_id_users"
    )
    assert user_foreign_key.ondelete is None


def test_refresh_token_model_matches_contract() -> None:
    refresh_token_model = _load_refresh_token_model()
    table = refresh_token_model.__table__

    assert table.metadata is Base.metadata
    assert table.name == "refresh_tokens"
    assert set(table.columns.keys()) == {
        "id",
        "session_id",
        "parent_token_id",
        "token_hash",
        "issued_at",
        "expires_at",
        "consumed_at",
    }

    id_column = table.c.id
    session_id_column = table.c.session_id
    parent_token_id_column = table.c.parent_token_id
    token_hash_column = table.c.token_hash
    issued_at_column = table.c.issued_at
    expires_at_column = table.c.expires_at
    consumed_at_column = table.c.consumed_at

    assert isinstance(id_column.type, PGUUID)
    assert id_column.primary_key is True
    assert id_column.nullable is False

    assert isinstance(session_id_column.type, PGUUID)
    assert session_id_column.nullable is False

    assert isinstance(parent_token_id_column.type, PGUUID)
    assert parent_token_id_column.nullable is True

    assert isinstance(token_hash_column.type, LargeBinary)
    assert token_hash_column.nullable is False

    for timestamp_column in (
        issued_at_column,
        expires_at_column,
        consumed_at_column,
    ):
        assert isinstance(timestamp_column.type, DateTime)
        assert timestamp_column.type.timezone is True

    assert issued_at_column.nullable is False
    assert expires_at_column.nullable is False
    assert consumed_at_column.nullable is True

    constraints = {
        constraint.name: constraint
        for constraint in table.constraints
    }

    assert set(constraints) == {
        "pk_refresh_tokens",
        "fk_refresh_tokens_session_id_refresh_sessions",
        "fk_refresh_tokens_parent_token_id_refresh_tokens",
        "uq_refresh_tokens_token_hash",
        "uq_refresh_tokens_parent_token_id",
        "ck_refresh_tokens_hash_length",
        "ck_refresh_tokens_expiry",
    }

    assert isinstance(
        constraints["pk_refresh_tokens"],
        PrimaryKeyConstraint,
    )
    assert isinstance(
        constraints["fk_refresh_tokens_session_id_refresh_sessions"],
        ForeignKeyConstraint,
    )
    assert isinstance(
        constraints["fk_refresh_tokens_parent_token_id_refresh_tokens"],
        ForeignKeyConstraint,
    )
    assert isinstance(
        constraints["uq_refresh_tokens_token_hash"],
        UniqueConstraint,
    )
    assert isinstance(
        constraints["uq_refresh_tokens_parent_token_id"],
        UniqueConstraint,
    )
    assert isinstance(
        constraints["ck_refresh_tokens_hash_length"],
        CheckConstraint,
    )
    assert isinstance(
        constraints["ck_refresh_tokens_expiry"],
        CheckConstraint,
    )

    assert [
        column.name
        for column in constraints["uq_refresh_tokens_token_hash"].columns
    ] == ["token_hash"]
    assert [
        column.name
        for column in constraints["uq_refresh_tokens_parent_token_id"].columns
    ] == ["parent_token_id"]

    foreign_keys = {
        foreign_key.parent.name: foreign_key
        for foreign_key in table.foreign_keys
    }
    assert set(foreign_keys) == {"session_id", "parent_token_id"}

    session_foreign_key = foreign_keys["session_id"]
    assert session_foreign_key.target_fullname == "refresh_sessions.id"
    assert (
        session_foreign_key.constraint.name
        == "fk_refresh_tokens_session_id_refresh_sessions"
    )
    assert session_foreign_key.ondelete is None

    parent_foreign_key = foreign_keys["parent_token_id"]
    assert parent_foreign_key.target_fullname == "refresh_tokens.id"
    assert (
        parent_foreign_key.constraint.name
        == "fk_refresh_tokens_parent_token_id_refresh_tokens"
    )
    assert parent_foreign_key.ondelete is None

    assert (
        str(constraints["ck_refresh_tokens_hash_length"].sqltext)
        == "octet_length(token_hash) = 32"
    )
    assert (
        str(constraints["ck_refresh_tokens_expiry"].sqltext)
        == "expires_at > issued_at"
    )


def test_refresh_models_are_exported_and_registered_in_metadata() -> None:
    (
        exported_session_model,
        exported_token_model,
        exported_names,
    ) = _load_registered_refresh_models()

    from app.infrastructure.database.models.refresh import (
        RefreshSessionModel,
        RefreshTokenModel,
    )

    assert exported_session_model is RefreshSessionModel
    assert exported_token_model is RefreshTokenModel
    assert {
        "RefreshSessionModel",
        "RefreshTokenModel",
    }.issubset(set(exported_names))

    assert {
        "users",
        "user_credentials",
        "refresh_sessions",
        "refresh_tokens",
    }.issubset(set(Base.metadata.tables))


def test_refresh_session_mapper_preserves_all_fields_round_trip() -> None:
    session_to_model, model_to_session = _load_session_mappers()

    created_at = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
    absolute_expires_at = datetime(
        2026,
        8,
        31,
        20,
        0,
        tzinfo=UTC,
    )
    revoked_at = datetime(2026, 8, 31, 13, 0, tzinfo=UTC)

    record = RefreshSessionRecord(
        id=uuid4(),
        user_id=uuid4(),
        created_at=created_at,
        absolute_expires_at=absolute_expires_at,
        revoked_at=revoked_at,
    )

    model = session_to_model(record)

    assert isinstance(model, RefreshSessionModel)
    assert model.id == record.id
    assert model.user_id == record.user_id
    assert model.created_at == record.created_at
    assert model.absolute_expires_at == record.absolute_expires_at
    assert model.revoked_at == record.revoked_at

    restored = model_to_session(model)

    assert restored == record


@pytest.mark.parametrize(
    ("parent_token_id", "consumed_at"),
    [
        pytest.param(None, None, id="nullable-fields"),
        pytest.param(
            uuid4(),
            datetime(2026, 8, 31, 12, 20, tzinfo=UTC),
            id="populated-fields",
        ),
    ],
)
def test_refresh_token_mapper_preserves_all_fields_round_trip(
    parent_token_id: UUID | None,
    consumed_at: datetime | None,
) -> None:
    token_to_model, model_to_token = _load_token_mappers()

    record = RefreshTokenRecord(
        id=uuid4(),
        session_id=uuid4(),
        parent_token_id=parent_token_id,
        token_hash=bytes(range(32)),
        issued_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        expires_at=datetime(2026, 8, 31, 12, 30, tzinfo=UTC),
        consumed_at=consumed_at,
    )

    model = token_to_model(record)

    assert isinstance(model, RefreshTokenModel)
    assert model.id == record.id
    assert model.session_id == record.session_id
    assert model.parent_token_id == record.parent_token_id
    assert model.token_hash == record.token_hash
    assert model.issued_at == record.issued_at
    assert model.expires_at == record.expires_at
    assert model.consumed_at == record.consumed_at

    restored = model_to_token(model)

    assert restored == record


def test_refresh_repository_error_is_runtime_error_contract() -> None:
    repository_error_cls = _load_refresh_repository_error()

    from app.application.security.refresh import (
        InvalidRefreshTokenError,
        RefreshAuthenticationError,
    )

    assert issubclass(repository_error_cls, RuntimeError)
    assert repository_error_cls is not RefreshAuthenticationError
    assert repository_error_cls is not InvalidRefreshTokenError

    err = repository_error_cls("persistence failed")
    assert str(err) == "persistence failed"


@pytest.mark.asyncio
async def test_add_session_adds_mapped_model_and_flushes_without_transactional_methods() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    repo = repo_cls(mock_session)

    record = RefreshSessionRecord(
        id=uuid4(),
        user_id=uuid4(),
        created_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        absolute_expires_at=datetime(2026, 8, 31, 20, 0, tzinfo=UTC),
        revoked_at=None,
    )

    await repo.add_session(record)

    mock_session.add.assert_called_once()
    added_model = mock_session.add.call_args[0][0]
    assert isinstance(added_model, RefreshSessionModel)
    assert added_model.id == record.id
    assert added_model.user_id == record.user_id
    assert added_model.created_at == record.created_at
    assert added_model.absolute_expires_at == record.absolute_expires_at
    assert added_model.revoked_at == record.revoked_at

    mock_session.flush.assert_awaited_once()
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()
    mock_session.close.assert_not_called()


@pytest.mark.asyncio
async def test_add_session_wraps_sqlalchemy_error_in_sanitized_repository_error() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.flush.side_effect = SQLAlchemyError("sensitive database detail")
    repo = repo_cls(mock_session)

    record = RefreshSessionRecord(
        id=uuid4(),
        user_id=uuid4(),
        created_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        absolute_expires_at=datetime(2026, 8, 31, 20, 0, tzinfo=UTC),
        revoked_at=None,
    )

    with pytest.raises(RefreshRepositoryError) as exc_info:
        await repo.add_session(record)

    err = exc_info.value
    assert str(err) == "refresh persistence failed"
    assert "sensitive database detail" not in str(err)
    assert isinstance(err.__cause__, SQLAlchemyError)
    assert str(err.__cause__) == "sensitive database detail"
    mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_add_token_adds_mapped_model_and_flushes_without_transactional_methods() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    repo = repo_cls(mock_session)

    record = RefreshTokenRecord(
        id=uuid4(),
        session_id=uuid4(),
        parent_token_id=uuid4(),
        token_hash=bytes(range(32)),
        issued_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        expires_at=datetime(2026, 8, 31, 12, 30, tzinfo=UTC),
        consumed_at=datetime(2026, 8, 31, 12, 20, tzinfo=UTC),
    )

    await repo.add_token(record)

    mock_session.add.assert_called_once()
    added_model = mock_session.add.call_args[0][0]
    assert isinstance(added_model, RefreshTokenModel)
    assert added_model.id == record.id
    assert added_model.session_id == record.session_id
    assert added_model.parent_token_id == record.parent_token_id
    assert added_model.token_hash == record.token_hash
    assert added_model.issued_at == record.issued_at
    assert added_model.expires_at == record.expires_at
    assert added_model.consumed_at == record.consumed_at

    mock_session.flush.assert_awaited_once()
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()
    mock_session.close.assert_not_called()


@pytest.mark.asyncio
async def test_add_token_wraps_sqlalchemy_error_in_sanitized_repository_error() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.flush.side_effect = SQLAlchemyError("sensitive database detail")
    repo = repo_cls(mock_session)

    record = RefreshTokenRecord(
        id=uuid4(),
        session_id=uuid4(),
        parent_token_id=None,
        token_hash=bytes(range(32)),
        issued_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        expires_at=datetime(2026, 8, 31, 12, 30, tzinfo=UTC),
        consumed_at=None,
    )

    with pytest.raises(RefreshRepositoryError) as exc_info:
        await repo.add_token(record)

    err = exc_info.value
    assert str(err) == "refresh persistence failed"
    assert "sensitive database detail" not in str(err)
    assert isinstance(err.__cause__, SQLAlchemyError)
    assert str(err.__cause__) == "sensitive database detail"
    mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_find_token_by_hash_executes_select_and_returns_mapped_record_without_lock() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    token_hash = bytes(range(32))

    mock_model = RefreshTokenModel(
        id=uuid4(),
        session_id=uuid4(),
        parent_token_id=uuid4(),
        token_hash=token_hash,
        issued_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        expires_at=datetime(2026, 8, 31, 12, 30, tzinfo=UTC),
        consumed_at=datetime(2026, 8, 31, 12, 20, tzinfo=UTC),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_model
    mock_session.execute.return_value = mock_result

    repo = repo_cls(mock_session)

    result = await repo.find_token_by_hash(token_hash)

    assert isinstance(result, RefreshTokenRecord)
    assert result.id == mock_model.id
    assert result.session_id == mock_model.session_id
    assert result.parent_token_id == mock_model.parent_token_id
    assert result.token_hash == mock_model.token_hash
    assert result.issued_at == mock_model.issued_at
    assert result.expires_at == mock_model.expires_at
    assert result.consumed_at == mock_model.consumed_at

    mock_session.execute.assert_awaited_once()
    stmt = mock_session.execute.call_args[0][0]
    assert "from refresh_tokens" in str(stmt).lower()
    assert "for update" not in str(stmt).lower()

    mock_session.flush.assert_not_called()
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()
    mock_session.close.assert_not_called()


@pytest.mark.asyncio
async def test_find_token_by_hash_returns_none_when_scalar_one_or_none_is_none() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = repo_cls(mock_session)

    result = await repo.find_token_by_hash(bytes(range(32)))

    assert result is None
    mock_session.execute.assert_awaited_once()
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_find_token_by_hash_wraps_sqlalchemy_error_in_sanitized_repository_error() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = SQLAlchemyError("sensitive database detail")
    repo = repo_cls(mock_session)

    with pytest.raises(RefreshRepositoryError) as exc_info:
        await repo.find_token_by_hash(bytes(range(32)))

    err = exc_info.value
    assert str(err) == "refresh lookup failed"
    assert "sensitive database detail" not in str(err)
    assert isinstance(err.__cause__, SQLAlchemyError)
    assert str(err.__cause__) == "sensitive database detail"
    mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_lock_session_executes_select_for_update_and_returns_mapped_record() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    session_id = uuid4()

    mock_model = RefreshSessionModel(
        id=session_id,
        user_id=uuid4(),
        created_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        absolute_expires_at=datetime(2026, 8, 31, 20, 0, tzinfo=UTC),
        revoked_at=None,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_model
    mock_session.execute.return_value = mock_result

    repo = repo_cls(mock_session)

    result = await repo.lock_session(session_id)

    assert isinstance(result, RefreshSessionRecord)
    assert result.id == mock_model.id
    assert result.user_id == mock_model.user_id
    assert result.created_at == mock_model.created_at
    assert result.absolute_expires_at == mock_model.absolute_expires_at
    assert result.revoked_at == mock_model.revoked_at

    mock_session.execute.assert_awaited_once()
    stmt = mock_session.execute.call_args[0][0]
    assert "from refresh_sessions" in str(stmt).lower()
    assert "for update" in str(stmt).lower()

    mock_session.flush.assert_not_called()
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()
    mock_session.close.assert_not_called()


@pytest.mark.asyncio
async def test_lock_session_returns_none_when_session_not_found() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = repo_cls(mock_session)

    result = await repo.lock_session(uuid4())

    assert result is None
    mock_session.execute.assert_awaited_once()
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_lock_session_wraps_sqlalchemy_error_in_sanitized_repository_error() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = SQLAlchemyError("sensitive database detail")
    repo = repo_cls(mock_session)

    with pytest.raises(RefreshRepositoryError) as exc_info:
        await repo.lock_session(uuid4())

    err = exc_info.value
    assert str(err) == "refresh lookup failed"
    assert "sensitive database detail" not in str(err)
    assert isinstance(err.__cause__, SQLAlchemyError)
    assert str(err.__cause__) == "sensitive database detail"
    mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_lock_token_executes_select_for_update_and_returns_mapped_record() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    token_id = uuid4()

    mock_model = RefreshTokenModel(
        id=token_id,
        session_id=uuid4(),
        parent_token_id=uuid4(),
        token_hash=bytes(range(32)),
        issued_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        expires_at=datetime(2026, 8, 31, 12, 30, tzinfo=UTC),
        consumed_at=datetime(2026, 8, 31, 12, 20, tzinfo=UTC),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_model
    mock_session.execute.return_value = mock_result

    repo = repo_cls(mock_session)

    result = await repo.lock_token(token_id)

    assert isinstance(result, RefreshTokenRecord)
    assert result.id == mock_model.id
    assert result.session_id == mock_model.session_id
    assert result.parent_token_id == mock_model.parent_token_id
    assert result.token_hash == mock_model.token_hash
    assert result.issued_at == mock_model.issued_at
    assert result.expires_at == mock_model.expires_at
    assert result.consumed_at == mock_model.consumed_at

    mock_session.execute.assert_awaited_once()
    stmt = mock_session.execute.call_args[0][0]
    assert "from refresh_tokens" in str(stmt).lower()
    assert "for update" in str(stmt).lower()

    mock_session.flush.assert_not_called()
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()
    mock_session.close.assert_not_called()


@pytest.mark.asyncio
async def test_lock_token_returns_none_when_token_not_found() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = repo_cls(mock_session)

    result = await repo.lock_token(uuid4())

    assert result is None
    mock_session.execute.assert_awaited_once()
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_lock_token_wraps_sqlalchemy_error_in_sanitized_repository_error() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = SQLAlchemyError("sensitive database detail")
    repo = repo_cls(mock_session)

    with pytest.raises(RefreshRepositoryError) as exc_info:
        await repo.lock_token(uuid4())

    err = exc_info.value
    assert str(err) == "refresh lookup failed"
    assert "sensitive database detail" not in str(err)
    assert isinstance(err.__cause__, SQLAlchemyError)
    assert str(err.__cause__) == "sensitive database detail"
    mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_mark_token_consumed_executes_update_and_flushes_without_transactional_methods() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    token_id = uuid4()
    consumed_at = datetime(2026, 8, 31, 12, 20, tzinfo=UTC)

    repo = repo_cls(mock_session)

    await repo.mark_token_consumed(token_id, consumed_at)

    mock_session.execute.assert_awaited_once()
    stmt = mock_session.execute.call_args[0][0]
    assert "update refresh_tokens" in str(stmt).lower()
    assert "consumed_at" in str(stmt).lower()
    assert "for update" not in str(stmt).lower()

    mock_session.flush.assert_awaited_once()
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()
    mock_session.close.assert_not_called()


@pytest.mark.parametrize("error_location", ["execute", "flush"])
@pytest.mark.asyncio
async def test_mark_token_consumed_wraps_sqlalchemy_error_in_sanitized_repository_error(
    error_location: str,
) -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    if error_location == "execute":
        mock_session.execute.side_effect = SQLAlchemyError("sensitive database detail")
    else:
        mock_session.flush.side_effect = SQLAlchemyError("sensitive database detail")

    repo = repo_cls(mock_session)

    with pytest.raises(RefreshRepositoryError) as exc_info:
        await repo.mark_token_consumed(uuid4(), datetime(2026, 8, 31, 12, 20, tzinfo=UTC))

    err = exc_info.value
    assert str(err) == "refresh update failed"
    assert "sensitive database detail" not in str(err)
    assert isinstance(err.__cause__, SQLAlchemyError)
    assert str(err.__cause__) == "sensitive database detail"
    mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_revoke_session_executes_update_with_revoked_at_null_condition_and_flushes() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    session_id = uuid4()
    revoked_at = datetime(2026, 8, 31, 13, 0, tzinfo=UTC)

    repo = repo_cls(mock_session)

    await repo.revoke_session(session_id, revoked_at)

    mock_session.execute.assert_awaited_once()
    stmt = mock_session.execute.call_args[0][0]
    assert "update refresh_sessions" in str(stmt).lower()
    assert "revoked_at is null" in str(stmt).lower()
    assert "for update" not in str(stmt).lower()

    mock_session.flush.assert_awaited_once()
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()
    mock_session.close.assert_not_called()


@pytest.mark.parametrize("error_location", ["execute", "flush"])
@pytest.mark.asyncio
async def test_revoke_session_wraps_sqlalchemy_error_in_sanitized_repository_error(
    error_location: str,
) -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    if error_location == "execute":
        mock_session.execute.side_effect = SQLAlchemyError("sensitive database detail")
    else:
        mock_session.flush.side_effect = SQLAlchemyError("sensitive database detail")

    repo = repo_cls(mock_session)

    with pytest.raises(RefreshRepositoryError) as exc_info:
        await repo.revoke_session(uuid4(), datetime(2026, 8, 31, 13, 0, tzinfo=UTC))

    err = exc_info.value
    assert str(err) == "refresh update failed"
    assert "sensitive database detail" not in str(err)
    assert isinstance(err.__cause__, SQLAlchemyError)
    assert str(err.__cause__) == "sensitive database detail"
    mock_session.rollback.assert_not_called()


def test_sqlalchemy_refresh_repository_structurally_satisfies_refresh_repository_protocol() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    from app.application.security.refresh import RefreshRepository

    def build_repository(session: AsyncSession) -> RefreshRepository:
        return repo_cls(session)

    mock_session = AsyncMock(spec=AsyncSession)
    repo = build_repository(mock_session)
    assert isinstance(repo, repo_cls)


@pytest.mark.asyncio
async def test_mark_token_consumed_ignores_zero_rowcount() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_session.execute.return_value = mock_result

    repo = repo_cls(mock_session)

    res = await repo.mark_token_consumed(uuid4(), datetime(2026, 8, 31, 12, 20, tzinfo=UTC))

    assert res is None
    mock_session.execute.assert_awaited_once()
    mock_session.flush.assert_awaited_once()
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()
    mock_session.close.assert_not_called()


@pytest.mark.asyncio
async def test_revoke_session_ignores_zero_rowcount() -> None:
    repo_cls = _load_sqlalchemy_refresh_repository()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_session.execute.return_value = mock_result

    repo = repo_cls(mock_session)

    res = await repo.revoke_session(uuid4(), datetime(2026, 8, 31, 13, 0, tzinfo=UTC))

    assert res is None
    mock_session.execute.assert_awaited_once()
    mock_session.flush.assert_awaited_once()
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()
    mock_session.close.assert_not_called()
import base64
import hashlib
import inspect
import re
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any, cast, get_type_hints
from uuid import UUID

import pytest


def _load_issued_refresh_token() -> type[Any]:
    try:
        from app.application.security.refresh import IssuedRefreshToken
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"refresh contract is not implemented: {exc}")

    return IssuedRefreshToken


def _load_secure_refresh_token_service() -> type[Any]:
    try:
        from app.infrastructure.security.refresh_token_service import (
            SecureRefreshTokenService,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"refresh token service is not implemented: {exc}")

    return SecureRefreshTokenService


def _load_invalid_refresh_token_error() -> type[BaseException]:
    try:
        from app.application.security.refresh import InvalidRefreshTokenError
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"invalid refresh token contract is not implemented: {exc}")

    return cast(type[BaseException], InvalidRefreshTokenError)


def _load_refresh_session_record() -> type[Any]:
    try:
        from app.application.security.refresh import RefreshSessionRecord
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"refresh session record is not implemented: {exc}")

    return RefreshSessionRecord


def _load_refresh_token_record() -> type[Any]:
    try:
        from app.application.security.refresh import RefreshTokenRecord
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"refresh token record is not implemented: {exc}")

    return RefreshTokenRecord


def _load_refresh_token_service_protocol() -> type[Any]:
    try:
        from app.application.security.refresh import RefreshTokenService
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"refresh token service protocol is not implemented: {exc}")

    return RefreshTokenService


def _load_refresh_repository_protocol() -> type[Any]:
    try:
        from app.application.security.refresh import RefreshRepository
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"refresh repository protocol is not implemented: {exc}")

    return RefreshRepository


def _load_refresh_authentication_error() -> type[BaseException]:
    try:
        from app.application.security.refresh import RefreshAuthenticationError
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(
            f"refresh authentication error is not implemented: {exc}"
        )

    return cast(type[BaseException], RefreshAuthenticationError)


def test_issued_refresh_token_is_an_immutable_value_object() -> None:
    issued_refresh_token = _load_issued_refresh_token()

    issued = issued_refresh_token(
        raw_token="A" * 43,
        token_hash=b"\x00" * 32,
    )

    assert issued.raw_token == "A" * 43
    assert issued.token_hash == b"\x00" * 32

    with pytest.raises(FrozenInstanceError):
        issued.raw_token = "B" * 43


def test_issue_returns_canonical_token_with_hash_of_decoded_secret() -> None:
    refresh_token_service = _load_secure_refresh_token_service()
    service = refresh_token_service()

    issued = service.issue()

    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", issued.raw_token) is not None

    decoded_secret = base64.urlsafe_b64decode(issued.raw_token + "=")

    assert len(decoded_secret) == 32
    assert len(issued.token_hash) == 32
    assert issued.token_hash == hashlib.sha256(decoded_secret).digest()


def test_digest_returns_sha256_of_canonical_decoded_secret() -> None:
    refresh_token_service = _load_secure_refresh_token_service()
    service = refresh_token_service()

    raw_token = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
    expected_digest = bytes.fromhex(
        "630dcd2966c4336691125448bbb25b4f"
        "f412a49c732db2c8abc1b8581bd710dd"
    )

    assert service.digest(raw_token) == expected_digest


@pytest.mark.parametrize(
    "raw_token",
    [
        pytest.param(None, id="non-string"),
        pytest.param("", id="empty"),
        pytest.param("A" * 42, id="short"),
        pytest.param("A" * 44, id="long"),
        pytest.param(
            "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
            id="padded",
        ),
        pytest.param("A" * 42 + "+", id="plus"),
        pytest.param("A" * 42 + "/", id="slash"),
        pytest.param("A" * 42 + " ", id="whitespace"),
        pytest.param("A" * 42 + "B", id="noncanonical-pad-bits"),
    ],
)
def test_digest_rejects_invalid_or_noncanonical_tokens(
    raw_token: object,
) -> None:
    refresh_token_service = _load_secure_refresh_token_service()
    invalid_refresh_token_error = _load_invalid_refresh_token_error()
    service = refresh_token_service()

    with pytest.raises(
        invalid_refresh_token_error,
        match=r"^invalid refresh token$",
    ):
        service.digest(raw_token)

def test_issue_returns_distinct_tokens_and_hashes() -> None:
    refresh_token_service = _load_secure_refresh_token_service()
    service = refresh_token_service()

    first = service.issue()
    second = service.issue()

    assert first.raw_token != second.raw_token
    assert first.token_hash != second.token_hash


def test_digest_of_issued_token_matches_issued_hash() -> None:
    refresh_token_service = _load_secure_refresh_token_service()
    service = refresh_token_service()

    issued = service.issue()

    assert service.digest(issued.raw_token) == issued.token_hash


def test_refresh_session_record_is_an_immutable_application_record() -> None:
    refresh_session_record = _load_refresh_session_record()

    session_id = UUID("11111111-1111-4111-8111-111111111111")
    user_id = UUID("22222222-2222-4222-8222-222222222222")
    created_at = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    absolute_expires_at = datetime(2026, 9, 1, 20, 0, tzinfo=UTC)

    record = refresh_session_record(
        id=session_id,
        user_id=user_id,
        created_at=created_at,
        absolute_expires_at=absolute_expires_at,
        revoked_at=None,
    )

    assert record.id == session_id
    assert record.user_id == user_id
    assert record.created_at == created_at
    assert record.absolute_expires_at == absolute_expires_at
    assert record.revoked_at is None

    with pytest.raises(FrozenInstanceError):
        record.revoked_at = created_at


def test_refresh_token_record_is_an_immutable_application_record() -> None:
    refresh_token_record = _load_refresh_token_record()

    token_id = UUID("33333333-3333-4333-8333-333333333333")
    session_id = UUID("11111111-1111-4111-8111-111111111111")
    parent_token_id = UUID("44444444-4444-4444-8444-444444444444")
    token_hash = b"\xab" * 32
    issued_at = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    expires_at = datetime(2026, 9, 1, 12, 30, tzinfo=UTC)

    record = refresh_token_record(
        id=token_id,
        session_id=session_id,
        parent_token_id=parent_token_id,
        token_hash=token_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        consumed_at=None,
    )

    assert record.id == token_id
    assert record.session_id == session_id
    assert record.parent_token_id == parent_token_id
    assert record.token_hash == token_hash
    assert record.issued_at == issued_at
    assert record.expires_at == expires_at
    assert record.consumed_at is None

    with pytest.raises(FrozenInstanceError):
        record.consumed_at = issued_at


def test_refresh_token_service_protocol_declares_issue_and_digest() -> None:
    refresh_token_service = _load_refresh_token_service_protocol()
    issued_refresh_token = _load_issued_refresh_token()

    assert get_type_hints(refresh_token_service.issue) == {
        "return": issued_refresh_token,
    }
    assert get_type_hints(refresh_token_service.digest) == {
        "raw_token": str,
        "return": bytes,
    }


def test_refresh_repository_protocol_declares_async_persistence_contract() -> None:
    refresh_repository = _load_refresh_repository_protocol()
    refresh_session_record = _load_refresh_session_record()
    refresh_token_record = _load_refresh_token_record()

    expected_hints = {
        "add_session": {
            "record": refresh_session_record,
            "return": type(None),
        },
        "add_token": {
            "record": refresh_token_record,
            "return": type(None),
        },
        "find_token_by_hash": {
            "token_hash": bytes,
            "return": refresh_token_record | None,
        },
        "lock_session": {
            "session_id": UUID,
            "return": refresh_session_record | None,
        },
        "lock_token": {
            "token_id": UUID,
            "return": refresh_token_record | None,
        },
        "mark_token_consumed": {
            "token_id": UUID,
            "consumed_at": datetime,
            "return": type(None),
        },
        "revoke_session": {
            "session_id": UUID,
            "revoked_at": datetime,
            "return": type(None),
        },
    }

    for method_name, expected_method_hints in expected_hints.items():
        method = getattr(refresh_repository, method_name)

        assert inspect.iscoroutinefunction(method)
        assert get_type_hints(method) == expected_method_hints


def test_refresh_authentication_error_is_a_runtime_error() -> None:
    refresh_authentication_error = _load_refresh_authentication_error()

    error = refresh_authentication_error("refresh authentication failed")

    assert isinstance(error, RuntimeError)
    assert str(error) == "refresh authentication failed"
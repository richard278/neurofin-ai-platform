from datetime import UTC, datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.application.security.clock import Clock
from app.application.security.tokens import (
    AccessPrincipal,
    AccessTokenService,
    InvalidAccessTokenError,
    IssuedAccessToken,
)
from app.domain.entities.user import User, UserRole
from app.infrastructure.security.jwt_access_token_service import (
    JWTAccessTokenService,
)
from app.infrastructure.security.system_clock import SystemClock


class NaiveClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 8, 31, 12, 0, 0)  # noqa: DTZ001


class NonUTCClock(Clock):
    def now(self) -> datetime:
        tz_offset = timezone(timedelta(hours=2))
        return datetime(2026, 8, 31, 14, 0, 0, tzinfo=tz_offset)


class MutableClock(Clock):
    def __init__(self, current_time: datetime | None = None) -> None:
        self.current_time = current_time or datetime.now(UTC)

    def now(self) -> datetime:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += timedelta(seconds=seconds)


@pytest.fixture
def rsa_keys() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return priv_pem, pub_pem


@pytest.fixture
def other_rsa_keys() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return priv_pem, pub_pem


def test_clock_is_protocol() -> None:
    assert issubclass(Clock, Protocol)


def test_invalid_access_token_error_derives_from_runtime_error() -> None:
    assert issubclass(InvalidAccessTokenError, RuntimeError)
    assert not issubclass(InvalidAccessTokenError, TypeError)


def test_issued_access_token_exposes_raw_token() -> None:
    exp = datetime.now(UTC)
    jti = uuid4()
    issued = IssuedAccessToken(raw_token="header.payload.sig", expires_at=exp, jti=jti)

    assert issued.raw_token == "header.payload.sig"
    assert issued.expires_at == exp
    assert issued.jti == jti


def test_access_token_service_protocol_and_adapter_contract(
    rsa_keys: tuple[str, str],
) -> None:
    assert issubclass(AccessTokenService, Protocol)

    priv_pem, pub_pem = rsa_keys
    clock = SystemClock()
    service = JWTAccessTokenService(priv_pem, pub_pem, clock)

    assert hasattr(service, "issue")
    assert hasattr(service, "validate")
    assert not hasattr(service, "issue_token")
    assert not hasattr(service, "validate_token")

    user = User.create("richard@example.com", UserRole.ANALYST)
    issued = service.issue(user)
    assert isinstance(issued, IssuedAccessToken)

    principal = service.validate(issued.raw_token)
    assert isinstance(principal, AccessPrincipal)
    assert principal.user_id == user.id


def test_issue_requires_user_instance(rsa_keys: tuple[str, str]) -> None:
    priv_pem, pub_pem = rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, SystemClock())

    with pytest.raises(TypeError, match="user must be an instance of User"):
        service.issue("not-a-user")  # type: ignore[arg-type]


def test_issue_rejects_naive_clock(rsa_keys: tuple[str, str]) -> None:
    priv_pem, pub_pem = rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, NaiveClock())
    user = User.create("richard@example.com", UserRole.ANALYST)

    with pytest.raises(
        RuntimeError, match="System clock must return timezone-aware UTC datetime"
    ):
        service.issue(user)


def test_issue_rejects_non_utc_clock(rsa_keys: tuple[str, str]) -> None:
    priv_pem, pub_pem = rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, NonUTCClock())
    user = User.create("richard@example.com", UserRole.ANALYST)

    with pytest.raises(
        RuntimeError, match="System clock must return timezone-aware UTC datetime"
    ):
        service.issue(user)


def test_issue_jwt_payload_and_ttl_contract(rsa_keys: tuple[str, str]) -> None:
    priv_pem, pub_pem = rsa_keys
    start_time = datetime(2026, 8, 31, 12, 0, 0, tzinfo=UTC)
    clock = MutableClock(start_time)
    service = JWTAccessTokenService(priv_pem, pub_pem, clock)

    user = User.create("richard@example.com", UserRole.ADMIN)
    issued = service.issue(user)

    assert isinstance(issued.raw_token, str)
    assert issued.expires_at == start_time + timedelta(seconds=600)

    header = jwt.get_unverified_header(issued.raw_token)
    assert header["alg"] == "PS256"
    assert header["typ"] == "neurofin-access+jwt"

    unverified = jwt.decode(issued.raw_token, options={"verify_signature": False})
    assert set(unverified.keys()) == {"sub", "iss", "aud", "iat", "exp", "jti", "role"}
    assert unverified["iss"] == "urn:neurofin:auth"
    assert unverified["aud"] == "urn:neurofin:api"
    assert unverified["sub"] == str(user.id)
    assert unverified["role"] == "ADMIN"
    assert unverified["iat"] == int(start_time.timestamp())
    assert unverified["exp"] == int((start_time + timedelta(seconds=600)).timestamp())
    assert unverified["exp"] - unverified["iat"] == 600
    assert UUID(unverified["jti"]) == issued.jti


def test_issue_jti_is_unique_per_issuance(rsa_keys: tuple[str, str]) -> None:
    priv_pem, pub_pem = rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, SystemClock())
    user = User.create("richard@example.com", UserRole.ANALYST)

    token1 = service.issue(user)
    token2 = service.issue(user)

    assert token1.jti != token2.jti
    assert token1.raw_token != token2.raw_token


def test_validate_native_pyjwt_leeway_and_expiration(
    rsa_keys: tuple[str, str],
) -> None:
    priv_pem, pub_pem = rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, SystemClock())
    now = datetime.now(UTC)

    # 1. Expired ~10 seconds ago (within 30s leeway) -> ACCEPTED
    payload_exp_10s = {
        "iss": "urn:neurofin:auth",
        "aud": "urn:neurofin:api",
        "sub": str(uuid4()),
        "role": "ANALYST",
        "iat": int((now - timedelta(seconds=610)).timestamp()),
        "exp": int((now - timedelta(seconds=10)).timestamp()),
        "jti": str(uuid4()),
    }
    token_exp_10s = jwt.encode(
        payload_exp_10s,
        priv_pem,
        algorithm="PS256",
        headers={"typ": "neurofin-access+jwt"},
    )
    principal_exp_10s = service.validate(token_exp_10s)
    assert principal_exp_10s.user_id == UUID(payload_exp_10s["sub"])

    # 2. Expired ~60 seconds ago (outside 30s leeway) -> REJECTED
    payload_exp_60s = {
        "iss": "urn:neurofin:auth",
        "aud": "urn:neurofin:api",
        "sub": str(uuid4()),
        "role": "ANALYST",
        "iat": int((now - timedelta(seconds=660)).timestamp()),
        "exp": int((now - timedelta(seconds=60)).timestamp()),
        "jti": str(uuid4()),
    }
    token_exp_60s = jwt.encode(
        payload_exp_60s,
        priv_pem,
        algorithm="PS256",
        headers={"typ": "neurofin-access+jwt"},
    )
    with pytest.raises(InvalidAccessTokenError, match="token validation failed"):
        service.validate(token_exp_60s)

    # 3. iat ~10 seconds in future (within 30s leeway) -> ACCEPTED
    payload_future_10s = {
        "iss": "urn:neurofin:auth",
        "aud": "urn:neurofin:api",
        "sub": str(uuid4()),
        "role": "ANALYST",
        "iat": int((now + timedelta(seconds=10)).timestamp()),
        "exp": int((now + timedelta(seconds=610)).timestamp()),
        "jti": str(uuid4()),
    }
    token_future_10s = jwt.encode(
        payload_future_10s,
        priv_pem,
        algorithm="PS256",
        headers={"typ": "neurofin-access+jwt"},
    )
    principal_future_10s = service.validate(token_future_10s)
    assert principal_future_10s.user_id == UUID(payload_future_10s["sub"])

    # 4. iat ~60 seconds in future (outside 30s leeway) -> REJECTED
    payload_future_60s = {
        "iss": "urn:neurofin:auth",
        "aud": "urn:neurofin:api",
        "sub": str(uuid4()),
        "role": "ANALYST",
        "iat": int((now + timedelta(seconds=60)).timestamp()),
        "exp": int((now + timedelta(seconds=660)).timestamp()),
        "jti": str(uuid4()),
    }
    token_future_60s = jwt.encode(
        payload_future_60s,
        priv_pem,
        algorithm="PS256",
        headers={"typ": "neurofin-access+jwt"},
    )
    with pytest.raises(InvalidAccessTokenError, match="token validation failed"):
        service.validate(token_future_60s)


def test_validate_rejects_altered_signature(
    rsa_keys: tuple[str, str], other_rsa_keys: tuple[str, str]
) -> None:
    priv_pem, pub_pem = rsa_keys
    other_priv_pem, _ = other_rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, SystemClock())
    service_other = JWTAccessTokenService(other_priv_pem, pub_pem, SystemClock())

    user = User.create("richard@example.com", UserRole.ANALYST)
    legit = service.issue(user)
    other = service_other.issue(user)

    parts = legit.raw_token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.invalid_signature"

    with pytest.raises(InvalidAccessTokenError, match="token validation failed"):
        service.validate(tampered)

    with pytest.raises(InvalidAccessTokenError, match="token validation failed"):
        service.validate(other.raw_token)


def test_validate_rejects_incorrect_issuer_or_audience(
    rsa_keys: tuple[str, str],
) -> None:
    priv_pem, pub_pem = rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, SystemClock())
    now = datetime.now(UTC)

    base = {
        "iss": "urn:neurofin:auth",
        "aud": "urn:neurofin:api",
        "sub": str(uuid4()),
        "role": "ANALYST",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=600)).timestamp()),
        "jti": str(uuid4()),
    }

    # Wrong iss
    bad_iss = dict(base, iss="urn:wrong:auth")
    token_bad_iss = jwt.encode(
        bad_iss, priv_pem, algorithm="PS256", headers={"typ": "neurofin-access+jwt"}
    )
    with pytest.raises(InvalidAccessTokenError):
        service.validate(token_bad_iss)

    # Wrong aud
    bad_aud = dict(base, aud="urn:wrong:api")
    token_bad_aud = jwt.encode(
        bad_aud, priv_pem, algorithm="PS256", headers={"typ": "neurofin-access+jwt"}
    )
    with pytest.raises(InvalidAccessTokenError):
        service.validate(token_bad_aud)


def test_validate_rejects_missing_mandatory_claims(rsa_keys: tuple[str, str]) -> None:
    priv_pem, pub_pem = rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, SystemClock())
    now = datetime.now(UTC)

    base = {
        "iss": "urn:neurofin:auth",
        "aud": "urn:neurofin:api",
        "sub": str(uuid4()),
        "role": "ANALYST",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=600)).timestamp()),
        "jti": str(uuid4()),
    }

    for key in base:
        incomplete = dict(base)
        del incomplete[key]
        token = jwt.encode(
            incomplete,
            priv_pem,
            algorithm="PS256",
            headers={"typ": "neurofin-access+jwt"},
        )
        with pytest.raises(InvalidAccessTokenError):
            service.validate(token)


def test_validate_rejects_invalid_claim_formats(rsa_keys: tuple[str, str]) -> None:
    priv_pem, pub_pem = rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, SystemClock())
    now = datetime.now(UTC)

    base = {
        "iss": "urn:neurofin:auth",
        "aud": "urn:neurofin:api",
        "sub": str(uuid4()),
        "role": "ANALYST",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=600)).timestamp()),
        "jti": str(uuid4()),
    }

    # Bad sub UUID
    token_bad_sub = jwt.encode(
        dict(base, sub="invalid-uuid"),
        priv_pem,
        algorithm="PS256",
        headers={"typ": "neurofin-access+jwt"},
    )
    with pytest.raises(InvalidAccessTokenError):
        service.validate(token_bad_sub)

    # Bad jti UUID
    token_bad_jti = jwt.encode(
        dict(base, jti="invalid-uuid"),
        priv_pem,
        algorithm="PS256",
        headers={"typ": "neurofin-access+jwt"},
    )
    with pytest.raises(InvalidAccessTokenError):
        service.validate(token_bad_jti)

    # Bad role
    token_bad_role = jwt.encode(
        dict(base, role="SUPERADMIN"),
        priv_pem,
        algorithm="PS256",
        headers={"typ": "neurofin-access+jwt"},
    )
    with pytest.raises(InvalidAccessTokenError):
        service.validate(token_bad_role)


def test_validate_rejects_other_algorithms(rsa_keys: tuple[str, str]) -> None:
    priv_pem, pub_pem = rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, SystemClock())
    now = datetime.now(UTC)

    base = {
        "iss": "urn:neurofin:auth",
        "aud": "urn:neurofin:api",
        "sub": str(uuid4()),
        "role": "ANALYST",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=600)).timestamp()),
        "jti": str(uuid4()),
    }

    # RS256
    rs256_token = jwt.encode(
        base, priv_pem, algorithm="RS256", headers={"typ": "neurofin-access+jwt"}
    )
    with pytest.raises(InvalidAccessTokenError):
        service.validate(rs256_token)

    # HS256 with key length >= 32 bytes to avoid InsecureKeyLengthWarning
    secret_key_32bytes = "a_very_long_secret_key_32bytes_long!"
    hs256_token = jwt.encode(
        base,
        secret_key_32bytes,
        algorithm="HS256",
        headers={"typ": "neurofin-access+jwt"},
    )
    with pytest.raises(InvalidAccessTokenError):
        service.validate(hs256_token)

    # none
    none_token = jwt.encode(
        base, "", algorithm="none", headers={"typ": "neurofin-access+jwt"}
    )
    with pytest.raises(InvalidAccessTokenError):
        service.validate(none_token)


def test_validate_rejects_incorrect_typ_header(rsa_keys: tuple[str, str]) -> None:
    priv_pem, pub_pem = rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, SystemClock())
    now = datetime.now(UTC)

    base = {
        "iss": "urn:neurofin:auth",
        "aud": "urn:neurofin:api",
        "sub": str(uuid4()),
        "role": "ANALYST",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=600)).timestamp()),
        "jti": str(uuid4()),
    }

    wrong_typ_token = jwt.encode(
        base, priv_pem, algorithm="PS256", headers={"typ": "JWT"}
    )
    with pytest.raises(InvalidAccessTokenError):
        service.validate(wrong_typ_token)


def test_validate_rejects_malformed_token_string(rsa_keys: tuple[str, str]) -> None:
    priv_pem, pub_pem = rsa_keys
    service = JWTAccessTokenService(priv_pem, pub_pem, SystemClock())

    with pytest.raises(InvalidAccessTokenError):
        service.validate("not-a-jwt")

    with pytest.raises(InvalidAccessTokenError):
        service.validate("")


def test_validate_does_not_convert_unhandled_runtime_error(
    rsa_keys: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key_pem, public_key_pem = rsa_keys
    service = JWTAccessTokenService(
        private_key_pem,
        public_key_pem,
        SystemClock(),
    )
    user = User.create("richard@example.com", UserRole.ANALYST)
    raw_token = service.issue(user).raw_token

    def broken_decode(
        *_args: object,
        **_kwargs: object,
    ) -> dict[str, object]:
        raise RuntimeError("Internal decoder failure")

    monkeypatch.setattr(jwt, "decode", broken_decode)

    with pytest.raises(
        RuntimeError,
        match="Internal decoder failure",
    ):
        service.validate(raw_token)


def test_validate_rejects_out_of_range_numeric_date(
    rsa_keys: tuple[str, str],
) -> None:
    private_key_pem, public_key_pem = rsa_keys
    service = JWTAccessTokenService(
        private_key_pem,
        public_key_pem,
        SystemClock(),
    )
    now = datetime.now(UTC)

    payload = {
        "iss": "urn:neurofin:auth",
        "aud": "urn:neurofin:api",
        "sub": str(uuid4()),
        "role": "ANALYST",
        "iat": int(now.timestamp()),
        "exp": 10**30,
        "jti": str(uuid4()),
    }

    raw_token = jwt.encode(
        payload,
        private_key_pem,
        algorithm="PS256",
        headers={"typ": "neurofin-access+jwt"},
    )

    with pytest.raises(
        InvalidAccessTokenError,
        match="token validation failed",
    ):
        service.validate(raw_token)

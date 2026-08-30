from uuid import uuid4

import pytest
from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.low_level import Type

from app.application.security.credentials import (
    CredentialAlreadyExistsError,
    CredentialRepositoryError,
    PasswordCredential,
)
from app.application.security.passwords import PasswordHasher, PasswordHashError
from app.core.config import Settings
from app.infrastructure.security.argon2_password_hasher import Argon2idPasswordHasher
from scripts.benchmark_argon2 import nearest_rank_percentile


def test_argon2_candidate_settings_are_explicit() -> None:
    settings = Settings(_env_file=None)

    assert settings.argon2_memory_cost_kib == 65536
    assert settings.argon2_time_cost == 3
    assert settings.argon2_parallelism == 4
    assert settings.argon2_hash_len == 32
    assert settings.argon2_salt_len == 16
    assert settings.auth_dummy_password_hash.startswith("$argon2id$")


def test_password_credential_is_opaque_application_data() -> None:
    credential = PasswordCredential(user_id=uuid4(), password_hash="$argon2id$opaque")

    assert credential.password_hash == "$argon2id$opaque"
    assert issubclass(CredentialAlreadyExistsError, CredentialRepositoryError)


def test_password_hasher_is_an_application_port() -> None:
    assert PasswordHasher.__module__ == "app.application.security.passwords"


def make_hasher() -> Argon2idPasswordHasher:
    return Argon2idPasswordHasher(Settings(_env_file=None))


def test_argon2id_hash_verify_and_salt_variation() -> None:
    hasher = make_hasher()

    first = hasher.hash("correct horse battery staple")
    second = hasher.hash("correct horse battery staple")

    assert first.startswith("$argon2id$")
    assert second.startswith("$argon2id$")
    assert first != second
    assert hasher.verify("correct horse battery staple", first) is True
    assert hasher.verify("wrong password", first) is False
    assert hasher.needs_rehash(first) is False


def test_argon2id_malformed_hash_fails_closed() -> None:
    hasher = make_hasher()

    with pytest.raises(PasswordHashError):
        hasher.verify("secret", "not-a-phc")

    with pytest.raises(PasswordHashError):
        hasher.needs_rehash("not-a-phc")


def test_dummy_phc_is_verifiable_and_current_policy() -> None:
    settings = Settings(_env_file=None)
    hasher = Argon2idPasswordHasher(settings)

    assert hasher.verify("unknown-user-probe", settings.auth_dummy_password_hash) is False
    assert hasher.needs_rehash(settings.auth_dummy_password_hash) is False


def test_nearest_rank_percentile_p95_calculation() -> None:
    samples = [float(value) for value in range(1, 21)]

    assert nearest_rank_percentile(samples, 0.95) == 19.0


def test_argon2id_needs_rehash_detects_policy_drift() -> None:
    hasher = make_hasher()
    legacy_hasher = Argon2PasswordHasher(
        time_cost=2,
        memory_cost=32768,
        parallelism=2,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    )
    legacy_hash = legacy_hasher.hash("policy drift")

    assert hasher.needs_rehash(legacy_hash) is True

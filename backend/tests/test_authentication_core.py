from uuid import UUID

import pytest

from app.application.security.authentication import (
    AuthenticateCommand,
    AuthenticateUser,
    AuthenticationError,
    AuthenticationResult,
    PasswordRehashCandidate,
)
from app.application.security.credentials import (
    CredentialRepository,
    PasswordCredential,
)
from app.application.security.passwords import PasswordHasher, PasswordHashError
from app.domain.entities.user import User, UserRole
from app.domain.repositories.user_repository import UserRepository

TEST_DUMMY_PHC = (
    "$argon2id$v=19$m=65536,t=3,p=4$Fl1Grf6vpX5SKg0514uA/w$"
    "B1b6Q8zwVQTD9GWQzzk6qXlmaYCjPcfUXI1rbfTDKRo"
)


def test_authentication_error_derives_from_runtime_error() -> None:
    assert issubclass(AuthenticationError, RuntimeError)
    assert not issubclass(AuthenticationError, ValueError)


class FakeUserRepository(UserRepository):
    def __init__(self) -> None:
        self.users_by_id: dict[UUID, User] = {}
        self.users_by_email: dict[str, User] = {}

    async def add(self, user: User) -> None:
        self.users_by_id[user.id] = user
        self.users_by_email[user.email] = user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users_by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return self.users_by_email.get(email)


class FakeCredentialRepository(CredentialRepository):
    def __init__(self) -> None:
        self.credentials: dict[UUID, PasswordCredential] = {}

    async def add(self, credential: PasswordCredential) -> None:
        self.credentials[credential.user_id] = credential

    async def get_by_user_id(self, user_id: UUID) -> PasswordCredential | None:
        return self.credentials.get(user_id)

    async def replace_hash(
        self, user_id: UUID, expected_hash: str, replacement_hash: str
    ) -> bool:
        cred = self.credentials.get(user_id)
        if cred and cred.password_hash == expected_hash:
            self.credentials[user_id] = PasswordCredential(
                user_id=user_id, password_hash=replacement_hash
            )
            return True
        return False


class FakePasswordHasher(PasswordHasher):
    def __init__(self) -> None:
        self.hashes: dict[str, str] = {}
        self.rehash_hashes: set[str] = set()
        self.dummy_verify_calls: int = 0

    def hash(self, password: str) -> str:
        return "$argon2id$v=19$m=65536,t=3,p=4$rehashed_salt$replacement_hash_bytes"

    def verify(self, password: str, encoded_hash: str) -> bool:
        if encoded_hash == TEST_DUMMY_PHC:
            self.dummy_verify_calls += 1
            return False
        if encoded_hash == "$argon2id$corrupt_dummy_hash":
            self.dummy_verify_calls += 1
            raise PasswordHashError("corrupt dummy hash configuration")
        if encoded_hash.startswith("$argon2id$invalid"):
            raise PasswordHashError("malformed phc")
        return self.hashes.get(password) == encoded_hash

    def needs_rehash(self, encoded_hash: str) -> bool:
        if encoded_hash.startswith("$argon2id$invalid"):
            raise PasswordHashError("malformed phc")
        return encoded_hash in self.rehash_hashes


@pytest.mark.asyncio
async def test_authenticate_command_and_result_contract() -> None:
    cmd = AuthenticateCommand(email="user@example.com", password="SecretPassword123!")
    assert cmd.email == "user@example.com"
    assert cmd.password == "SecretPassword123!"
    assert not hasattr(cmd, "raw_email")
    assert not hasattr(cmd, "raw_password")

    user = User.create("user@example.com", UserRole.ANALYST)
    res = AuthenticationResult(user=user, rehash=None)
    assert res.user == user
    assert res.rehash is None
    assert not hasattr(res, "rehash_candidate")


@pytest.mark.asyncio
async def test_authenticate_user_constructor_requires_dummy_password_hash() -> None:
    user_repo = FakeUserRepository()
    cred_repo = FakeCredentialRepository()
    hasher = FakePasswordHasher()

    with pytest.raises(TypeError):
        AuthenticateUser(user_repo, cred_repo, hasher)  # type: ignore[call-arg]

    use_case = AuthenticateUser(user_repo, cred_repo, hasher, TEST_DUMMY_PHC)
    assert use_case is not None


@pytest.mark.asyncio
async def test_authenticate_user_success_without_rehash() -> None:
    user_repo = FakeUserRepository()
    cred_repo = FakeCredentialRepository()
    hasher = FakePasswordHasher()

    user = User.create("richard@example.com", UserRole.ANALYST)
    await user_repo.add(user)

    pwd_hash = hasher.hash("SecretPassword123!")
    hasher.hashes["SecretPassword123!"] = pwd_hash
    await cred_repo.add(PasswordCredential(user_id=user.id, password_hash=pwd_hash))

    use_case = AuthenticateUser(user_repo, cred_repo, hasher, TEST_DUMMY_PHC)
    cmd = AuthenticateCommand(
        email="  Richard@Example.COM  ", password="SecretPassword123!"
    )

    result = await use_case.execute(cmd)
    assert isinstance(result, AuthenticationResult)
    assert result.user == user
    assert result.rehash is None


@pytest.mark.asyncio
async def test_authenticate_user_success_with_rehash() -> None:
    user_repo = FakeUserRepository()
    cred_repo = FakeCredentialRepository()
    hasher = FakePasswordHasher()

    user = User.create("richard@example.com", UserRole.ADMIN)
    await user_repo.add(user)

    old_hash = "legacy_argon2id_hash"
    hasher.hashes["SecretPassword123!"] = old_hash
    hasher.rehash_hashes.add(old_hash)
    await cred_repo.add(PasswordCredential(user_id=user.id, password_hash=old_hash))

    use_case = AuthenticateUser(user_repo, cred_repo, hasher, TEST_DUMMY_PHC)
    cmd = AuthenticateCommand(
        email="richard@example.com", password="SecretPassword123!"
    )

    result = await use_case.execute(cmd)
    assert result.user == user
    assert result.rehash is not None
    assert isinstance(result.rehash, PasswordRehashCandidate)
    assert result.rehash.user_id == user.id
    assert result.rehash.expected_hash == old_hash
    assert (
        result.rehash.replacement_hash
        == "$argon2id$v=19$m=65536,t=3,p=4$rehashed_salt$replacement_hash_bytes"
    )
    assert "SecretPassword123!" not in str(result.rehash)


@pytest.mark.asyncio
async def test_dummy_verification_unknown_identity_prevents_enumeration() -> None:
    user_repo = FakeUserRepository()
    cred_repo = FakeCredentialRepository()
    hasher = FakePasswordHasher()

    use_case = AuthenticateUser(user_repo, cred_repo, hasher, TEST_DUMMY_PHC)
    cmd = AuthenticateCommand(
        email="nonexistent@example.com", password="AnyPassword123!"
    )

    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        await use_case.execute(cmd)

    assert hasher.dummy_verify_calls == 1


@pytest.mark.asyncio
async def test_dummy_verification_invalid_email_syntax_prevents_enumeration() -> None:
    user_repo = FakeUserRepository()
    cred_repo = FakeCredentialRepository()
    hasher = FakePasswordHasher()

    use_case = AuthenticateUser(user_repo, cred_repo, hasher, TEST_DUMMY_PHC)
    cmd = AuthenticateCommand(email="invalid-email", password="AnyPassword123!")

    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        await use_case.execute(cmd)

    assert hasher.dummy_verify_calls == 1


@pytest.mark.asyncio
async def test_dummy_verification_missing_credential_prevents_enumeration() -> None:
    user_repo = FakeUserRepository()
    cred_repo = FakeCredentialRepository()
    hasher = FakePasswordHasher()

    user = User.create("nocred@example.com", UserRole.ANALYST)
    await user_repo.add(user)

    use_case = AuthenticateUser(user_repo, cred_repo, hasher, TEST_DUMMY_PHC)
    cmd = AuthenticateCommand(email="nocred@example.com", password="AnyPassword123!")

    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        await use_case.execute(cmd)

    assert hasher.dummy_verify_calls == 1


@pytest.mark.asyncio
async def test_dummy_verification_corrupt_dummy_hash_raises_sanitized_runtime_error() -> None:
    user_repo = FakeUserRepository()
    cred_repo = FakeCredentialRepository()
    hasher = FakePasswordHasher()

    use_case = AuthenticateUser(
        user_repo, cred_repo, hasher, "$argon2id$corrupt_dummy_hash"
    )
    cmd = AuthenticateCommand(
        email="nonexistent@example.com", password="SuperSecretPassword123!"
    )

    with pytest.raises(RuntimeError) as exc_info:
        await use_case.execute(cmd)

    msg = str(exc_info.value)
    assert "SuperSecretPassword123!" not in msg
    assert "nonexistent@example.com" not in msg
    assert "$argon2id$corrupt_dummy_hash" not in msg
    assert "dummy password hash verification failed" in msg


@pytest.mark.asyncio
async def test_authenticate_user_malformed_phc_handled_gracefully() -> None:
    user_repo = FakeUserRepository()
    cred_repo = FakeCredentialRepository()
    hasher = FakePasswordHasher()

    user = User.create("user_bad_phc@example.com", UserRole.ANALYST)
    await user_repo.add(user)
    await cred_repo.add(
        PasswordCredential(user_id=user.id, password_hash="$argon2id$invalid_phc")
    )

    use_case = AuthenticateUser(user_repo, cred_repo, hasher, TEST_DUMMY_PHC)
    cmd = AuthenticateCommand(
        email="user_bad_phc@example.com", password="Password123!"
    )

    with pytest.raises(AuthenticationError, match="Invalid credentials") as exc_info:
        await use_case.execute(cmd)

    assert "invalid_phc" not in str(exc_info.value)
    assert "Password123!" not in str(exc_info.value)

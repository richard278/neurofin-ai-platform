from dataclasses import dataclass
from uuid import UUID

from app.application.security.credentials import CredentialRepository
from app.application.security.passwords import (
    PasswordHasher,
    PasswordHashError,
)
from app.domain.entities.user import (
    InvalidUserEmailError,
    User,
    canonicalize_user_email,
)
from app.domain.repositories.user_repository import UserRepository


class AuthenticationError(RuntimeError):
    """Raised when authentication fails for any reason."""



@dataclass(frozen=True)
class AuthenticateCommand:
    email: str
    password: str


@dataclass(frozen=True)
class PasswordRehashCandidate:
    user_id: UUID
    expected_hash: str
    replacement_hash: str


@dataclass(frozen=True)
class AuthenticationResult:
    user: User
    rehash: PasswordRehashCandidate | None = None


class AuthenticateUser:
    def __init__(
        self,
        user_repository: UserRepository,
        credential_repository: CredentialRepository,
        password_hasher: PasswordHasher,
        dummy_password_hash: str,
    ) -> None:
        self._user_repository = user_repository
        self._credential_repository = credential_repository
        self._password_hasher = password_hasher
        self._dummy_password_hash = dummy_password_hash

    async def execute(self, command: AuthenticateCommand) -> AuthenticationResult:
        if not isinstance(command, AuthenticateCommand):
            raise TypeError("command must be AuthenticateCommand")

        # 1. Canonicalize email
        try:
            canonical_email = canonicalize_user_email(command.email)
            email_valid = True
        except InvalidUserEmailError:
            email_valid = False
            canonical_email = ""

        if not email_valid:
            self._perform_dummy_verification(command.password)
            raise AuthenticationError("Invalid credentials")

        # 2. Lookup user
        user = await self._user_repository.get_by_email(canonical_email)
        if user is None:
            self._perform_dummy_verification(command.password)
            raise AuthenticationError("Invalid credentials")

        # 3. Lookup credential
        credential = await self._credential_repository.get_by_user_id(user.id)
        if credential is None:
            self._perform_dummy_verification(command.password)
            raise AuthenticationError("Invalid credentials")

        # 4. Verify password
        try:
            is_valid = self._password_hasher.verify(
                command.password, credential.password_hash
            )
        except (PasswordHashError, ValueError):
            raise AuthenticationError("Invalid credentials") from None

        if not is_valid:
            raise AuthenticationError("Invalid credentials")

        # 5. Check rehash candidate
        rehash_candidate: PasswordRehashCandidate | None = None
        try:
            if self._password_hasher.needs_rehash(credential.password_hash):
                new_hash = self._password_hasher.hash(command.password)
                rehash_candidate = PasswordRehashCandidate(
                    user_id=user.id,
                    expected_hash=credential.password_hash,
                    replacement_hash=new_hash,
                )
        except (PasswordHashError, ValueError):
            rehash_candidate = None

        return AuthenticationResult(user=user, rehash=rehash_candidate)

    def _perform_dummy_verification(self, password: str) -> None:
        try:
            self._password_hasher.verify(password, self._dummy_password_hash)
        except (PasswordHashError, ValueError):
            raise RuntimeError(
                "dummy password hash verification failed due to invalid configuration"
            ) from None

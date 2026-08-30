from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import (
    HashingError,
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from argon2.low_level import Type

from app.application.security.passwords import PasswordHashError
from app.core.config import Settings


class Argon2idPasswordHasher:
    def __init__(self, settings: Settings) -> None:
        self._hasher = Argon2PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost_kib,
            parallelism=settings.argon2_parallelism,
            hash_len=settings.argon2_hash_len,
            salt_len=settings.argon2_salt_len,
            type=Type.ID,
        )

    def hash(self, password: str) -> str:
        try:
            return self._hasher.hash(password)
        except HashingError as exc:
            raise PasswordHashError("password hashing failed") from exc

    def verify(self, password: str, encoded_hash: str) -> bool:
        try:
            return self._hasher.verify(encoded_hash, password)
        except VerifyMismatchError:
            return False
        except (InvalidHashError, VerificationError) as exc:
            raise PasswordHashError("password verification failed") from exc

    def needs_rehash(self, encoded_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(encoded_hash)
        except (InvalidHashError, VerificationError) as exc:
            raise PasswordHashError("password hash inspection failed") from exc

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class CredentialRepositoryError(RuntimeError):
    pass


class CredentialAlreadyExistsError(CredentialRepositoryError):
    pass


@dataclass(frozen=True)
class PasswordCredential:
    user_id: UUID
    password_hash: str


class CredentialRepository(Protocol):
    async def add(self, credential: PasswordCredential) -> None:
        ...

    async def get_by_user_id(self, user_id: UUID) -> PasswordCredential | None:
        ...

    async def replace_hash(
        self,
        user_id: UUID,
        expected_hash: str,
        replacement_hash: str,
    ) -> bool:
        ...

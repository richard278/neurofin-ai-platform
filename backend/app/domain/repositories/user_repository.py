from abc import ABC, abstractmethod
from uuid import UUID

from ..entities.user import User


class UserRepositoryError(RuntimeError):
    pass


class UserAlreadyExistsError(UserRepositoryError):
    pass


class UserRepository(ABC):
    @abstractmethod
    async def add(self, user: User) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError

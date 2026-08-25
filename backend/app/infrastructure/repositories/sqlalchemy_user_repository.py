from collections.abc import Iterator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.domain.repositories.user_repository import (
    UserAlreadyExistsError,
    UserRepository,
    UserRepositoryError,
)
from app.infrastructure.database.mappers.user_mapper import user_to_domain, user_to_model
from app.infrastructure.database.models.user import UserModel

_IDENTITY_UNIQUE_CONSTRAINTS = {"pk_users", "uq_users_email"}


def _exception_chain(exc: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = exc

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current

        orig = getattr(current, "orig", None)
        if isinstance(orig, BaseException) and id(orig) not in seen:
            current = orig
            continue

        cause = current.__cause__
        if cause is not None and id(cause) not in seen:
            current = cause
            continue

        context = current.__context__
        if context is not None and id(context) not in seen:
            current = context
            continue

        current = None


def _structured_postgres_identity_conflict(exc: IntegrityError) -> bool:
    for candidate in _exception_chain(exc):
        sqlstate = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)

        constraint_name = getattr(candidate, "constraint_name", None)
        diag = getattr(candidate, "diag", None)
        if constraint_name is None and diag is not None:
            constraint_name = getattr(diag, "constraint_name", None)

        if sqlstate == "23505" and constraint_name in _IDENTITY_UNIQUE_CONSTRAINTS:
            return True

    return False


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        model = user_to_model(user)
        try:
            self._session.add(model)
            await self._session.flush()
        except IntegrityError as exc:
            if _structured_postgres_identity_conflict(exc):
                raise UserAlreadyExistsError("user identity already exists") from exc
            raise UserRepositoryError("user persistence failed") from exc
        except SQLAlchemyError as exc:
            raise UserRepositoryError("user persistence failed") from exc

    async def get_by_id(self, user_id: UUID) -> User | None:
        try:
            model = await self._session.get(UserModel, user_id)
        except SQLAlchemyError as exc:
            raise UserRepositoryError("user lookup failed") from exc

        return None if model is None else user_to_domain(model)

    async def get_by_email(self, email: str) -> User | None:
        statement = select(UserModel).where(UserModel.email == email)

        try:
            result = await self._session.execute(statement)
            model = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise UserRepositoryError("user lookup failed") from exc

        return None if model is None else user_to_domain(model)

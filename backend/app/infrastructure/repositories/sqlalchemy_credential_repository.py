from collections.abc import Iterator
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.security.credentials import (
    CredentialAlreadyExistsError,
    CredentialRepository,
    CredentialRepositoryError,
    PasswordCredential,
)
from app.infrastructure.database.mappers.credential_mapper import (
    credential_to_model,
    model_to_credential,
)
from app.infrastructure.database.models.user_credential import UserCredentialModel

_CREDENTIAL_PK_CONSTRAINT = "pk_user_credentials"


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


def _structured_postgres_credential_conflict(exc: IntegrityError) -> bool:
    for candidate in _exception_chain(exc):
        sqlstate = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)

        constraint_name = getattr(candidate, "constraint_name", None)
        diag = getattr(candidate, "diag", None)
        if constraint_name is None and diag is not None:
            constraint_name = getattr(diag, "constraint_name", None)

        if sqlstate == "23505" and constraint_name == _CREDENTIAL_PK_CONSTRAINT:
            return True

    return False


class SQLAlchemyCredentialRepository(CredentialRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, credential: PasswordCredential) -> None:
        model = credential_to_model(credential)
        try:
            self._session.add(model)
            await self._session.flush()
        except IntegrityError as exc:
            if _structured_postgres_credential_conflict(exc):
                raise CredentialAlreadyExistsError(
                    "credential already exists for user"
                ) from exc
            raise CredentialRepositoryError("credential persistence failed") from exc
        except SQLAlchemyError as exc:
            raise CredentialRepositoryError("credential persistence failed") from exc

    async def get_by_user_id(self, user_id: UUID) -> PasswordCredential | None:
        try:
            model = await self._session.get(UserCredentialModel, user_id)
        except SQLAlchemyError as exc:
            raise CredentialRepositoryError("credential lookup failed") from exc

        return None if model is None else model_to_credential(model)

    async def replace_hash(
        self,
        user_id: UUID,
        expected_hash: str,
        replacement_hash: str,
    ) -> bool:
        stmt = (
            update(UserCredentialModel)
            .where(
                UserCredentialModel.user_id == user_id,
                UserCredentialModel.password_hash == expected_hash,
            )
            .values(password_hash=replacement_hash)
        )
        try:
            result = await self._session.execute(stmt)
            rowcount = getattr(result, "rowcount", 0)
            return bool(rowcount == 1)
        except SQLAlchemyError as exc:
            raise CredentialRepositoryError("credential update failed") from exc

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.security.refresh import (
    RefreshRepositoryError,
    RefreshSessionRecord,
    RefreshTokenRecord,
)
from app.infrastructure.database.mappers.refresh_mapper import (
    model_to_session,
    model_to_token,
    session_to_model,
    token_to_model,
)
from app.infrastructure.database.models.refresh import (
    RefreshSessionModel,
    RefreshTokenModel,
)


class SQLAlchemyRefreshRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_session(self, record: RefreshSessionRecord) -> None:
        model = session_to_model(record)
        self._session.add(model)
        try:
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise RefreshRepositoryError("refresh persistence failed") from exc

    async def add_token(self, record: RefreshTokenRecord) -> None:
        model = token_to_model(record)
        self._session.add(model)
        try:
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise RefreshRepositoryError("refresh persistence failed") from exc

    async def find_token_by_hash(
        self,
        token_hash: bytes,
    ) -> RefreshTokenRecord | None:
        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.token_hash == token_hash
        )
        try:
            result = await self._session.execute(stmt)
        except SQLAlchemyError as exc:
            raise RefreshRepositoryError("refresh lookup failed") from exc

        model = result.scalar_one_or_none()
        if model is None:
            return None
        return model_to_token(model)

    async def lock_session(
        self,
        session_id: UUID,
    ) -> RefreshSessionRecord | None:
        stmt = (
            select(RefreshSessionModel)
            .where(RefreshSessionModel.id == session_id)
            .with_for_update()
        )
        try:
            result = await self._session.execute(stmt)
        except SQLAlchemyError as exc:
            raise RefreshRepositoryError("refresh lookup failed") from exc

        model = result.scalar_one_or_none()
        if model is None:
            return None
        return model_to_session(model)

    async def lock_token(
        self,
        token_id: UUID,
    ) -> RefreshTokenRecord | None:
        stmt = (
            select(RefreshTokenModel)
            .where(RefreshTokenModel.id == token_id)
            .with_for_update()
        )
        try:
            result = await self._session.execute(stmt)
        except SQLAlchemyError as exc:
            raise RefreshRepositoryError("refresh lookup failed") from exc

        model = result.scalar_one_or_none()
        if model is None:
            return None
        return model_to_token(model)

    async def mark_token_consumed(
        self,
        token_id: UUID,
        consumed_at: datetime,
    ) -> None:
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.id == token_id)
            .values(consumed_at=consumed_at)
        )
        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise RefreshRepositoryError("refresh update failed") from exc

    async def revoke_session(
        self,
        session_id: UUID,
        revoked_at: datetime,
    ) -> None:
        stmt = (
            update(RefreshSessionModel)
            .where(
                RefreshSessionModel.id == session_id,
                RefreshSessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise RefreshRepositoryError("refresh update failed") from exc

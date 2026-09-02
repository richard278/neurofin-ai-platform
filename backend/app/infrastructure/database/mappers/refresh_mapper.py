from app.application.security.refresh import (
    RefreshSessionRecord,
    RefreshTokenRecord,
)
from app.infrastructure.database.models.refresh import (
    RefreshSessionModel,
    RefreshTokenModel,
)


def session_to_model(record: RefreshSessionRecord) -> RefreshSessionModel:
    return RefreshSessionModel(
        id=record.id,
        user_id=record.user_id,
        created_at=record.created_at,
        absolute_expires_at=record.absolute_expires_at,
        revoked_at=record.revoked_at,
    )


def model_to_session(model: RefreshSessionModel) -> RefreshSessionRecord:
    return RefreshSessionRecord(
        id=model.id,
        user_id=model.user_id,
        created_at=model.created_at,
        absolute_expires_at=model.absolute_expires_at,
        revoked_at=model.revoked_at,
    )


def token_to_model(record: RefreshTokenRecord) -> RefreshTokenModel:
    return RefreshTokenModel(
        id=record.id,
        session_id=record.session_id,
        parent_token_id=record.parent_token_id,
        token_hash=record.token_hash,
        issued_at=record.issued_at,
        expires_at=record.expires_at,
        consumed_at=record.consumed_at,
    )


def model_to_token(model: RefreshTokenModel) -> RefreshTokenRecord:
    return RefreshTokenRecord(
        id=model.id,
        session_id=model.session_id,
        parent_token_id=model.parent_token_id,
        token_hash=model.token_hash,
        issued_at=model.issued_at,
        expires_at=model.expires_at,
        consumed_at=model.consumed_at,
    )

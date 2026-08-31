from app.application.security.credentials import PasswordCredential
from app.infrastructure.database.models.user_credential import UserCredentialModel


def credential_to_model(
    credential: PasswordCredential,
) -> UserCredentialModel:
    return UserCredentialModel(
        user_id=credential.user_id,
        password_hash=credential.password_hash,
    )


def model_to_credential(
    model: UserCredentialModel,
) -> PasswordCredential:
    return PasswordCredential(
        user_id=model.user_id,
        password_hash=model.password_hash,
    )

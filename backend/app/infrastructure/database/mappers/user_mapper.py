from ....domain.entities.user import User, UserRole
from ..models.user import UserModel


def user_to_model(user: User) -> UserModel:
    return UserModel(
        id=user.id,
        email=user.email,
        role=user.role.value,
    )


def user_to_domain(model: UserModel) -> User:
    role = UserRole(model.role)
    return User(
        id=model.id,
        email=model.email,
        role=role,
    )

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid4


class InvalidUserEmailError(ValueError):
    pass


class UserRole(StrEnum):
    ANALYST = "ANALYST"
    ADMIN = "ADMIN"


_ALLOWED_LOCAL = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789!#$%&'*+-/=?^_`{|}~."
)
_ALLOWED_DOMAIN_LABEL = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")


def _validate_email(email: str) -> None:
    if not isinstance(email, str):
        raise InvalidUserEmailError("email must be a string")

    try:
        email.encode("ascii")
    except UnicodeEncodeError as exc:
        raise InvalidUserEmailError("email must contain ASCII characters only") from exc

    if len(email) > 254:
        raise InvalidUserEmailError("email must not exceed 254 characters")

    if email.count("@") != 1:
        raise InvalidUserEmailError("email must contain exactly one @")

    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in email):
        raise InvalidUserEmailError("email must not contain whitespace or control characters")

    local, domain = email.split("@")

    if not 1 <= len(local) <= 64:
        raise InvalidUserEmailError("email local part must contain 1 to 64 characters")

    if local.startswith(".") or local.endswith(".") or ".." in local:
        raise InvalidUserEmailError("email local part has invalid dot placement")

    if any(char not in _ALLOWED_LOCAL for char in local):
        raise InvalidUserEmailError("email local part contains unsupported characters")

    if "." not in domain:
        raise InvalidUserEmailError("email domain must contain at least one dot")

    labels = domain.split(".")
    for label in labels:
        if not 1 <= len(label) <= 63:
            raise InvalidUserEmailError("email domain label must contain 1 to 63 characters")
        if label.startswith("-") or label.endswith("-"):
            raise InvalidUserEmailError("email domain label cannot start or end with hyphen")
        if any(char not in _ALLOWED_DOMAIN_LABEL for char in label):
            raise InvalidUserEmailError("email domain label contains unsupported characters")


def _canonicalize_email(raw_email: str) -> str:
    if not isinstance(raw_email, str):
        raise InvalidUserEmailError("email must be a string")

    canonical = raw_email.strip().lower()
    _validate_email(canonical)
    return canonical


@dataclass(frozen=True)
class User:
    id: UUID
    email: str
    role: UserRole

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be UUID")
        if not isinstance(self.role, UserRole):
            raise TypeError("role must be UserRole")

        _validate_email(self.email)
        if self.email.strip().lower() != self.email:
            raise InvalidUserEmailError("email must already be canonical")

    @classmethod
    def create(cls, raw_email: str, role: UserRole) -> "User":
        canonical_email = _canonicalize_email(raw_email)
        return cls(id=uuid4(), email=canonical_email, role=role)

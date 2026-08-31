from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from app.application.security.clock import Clock
from app.application.security.tokens import (
    AccessPrincipal,
    InvalidAccessTokenError,
    IssuedAccessToken,
)
from app.domain.entities.user import User, UserRole

_ALGORITHM = "PS256"
_TYP = "neurofin-access+jwt"
_ISSUER = "urn:neurofin:auth"
_AUDIENCE = "urn:neurofin:api"
_TTL_SECONDS = 600
_LEEWAY_SECONDS = 30
_MANDATORY_CLAIMS = ["sub", "iss", "aud", "iat", "exp", "jti", "role"]


class JWTAccessTokenService:
    def __init__(
        self,
        private_key_pem: str | bytes,
        public_key_pem: str | bytes,
        clock: Clock,
    ) -> None:
        self._private_key_pem = private_key_pem
        self._public_key_pem = public_key_pem
        self._clock = clock

    def issue(self, user: User) -> IssuedAccessToken:
        if not isinstance(user, User):
            raise TypeError("user must be an instance of User")

        now = self._clock.now()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise RuntimeError("System clock must return timezone-aware UTC datetime")

        expires_at = now + timedelta(seconds=_TTL_SECONDS)
        jti = uuid4()

        payload = {
            "iss": _ISSUER,
            "aud": _AUDIENCE,
            "sub": str(user.id),
            "role": user.role.value,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": str(jti),
        }

        token = jwt.encode(
            payload,
            self._private_key_pem,
            algorithm=_ALGORITHM,
            headers={"typ": _TYP},
        )

        return IssuedAccessToken(raw_token=token, expires_at=expires_at, jti=jti)

    def validate(self, raw_token: str) -> AccessPrincipal:
        if not isinstance(raw_token, str) or not raw_token:
            raise InvalidAccessTokenError("token validation failed")

        try:
            header = jwt.get_unverified_header(raw_token)
            if header.get("typ") != _TYP or header.get("alg") != _ALGORITHM:
                raise InvalidAccessTokenError("token validation failed")

            payload = jwt.decode(
                raw_token,
                self._public_key_pem,
                algorithms=[_ALGORITHM],
                issuer=_ISSUER,
                audience=_AUDIENCE,
                leeway=_LEEWAY_SECONDS,
                options={
                    "require": _MANDATORY_CLAIMS,
                    "strict_aud": True,
                },
            )

            user_id = UUID(payload["sub"])
            jti = UUID(payload["jti"])
            role = UserRole(payload["role"])
            try:
                issued_at = datetime.fromtimestamp(payload["iat"], tz=UTC)
                expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)
            except (OverflowError, OSError):
                raise InvalidAccessTokenError("token validation failed") from None

            return AccessPrincipal(
                user_id=user_id,
                role=role,
                issued_at=issued_at,
                expires_at=expires_at,
                jti=jti,
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, InvalidAccessTokenError):
                raise
            raise InvalidAccessTokenError("token validation failed") from None

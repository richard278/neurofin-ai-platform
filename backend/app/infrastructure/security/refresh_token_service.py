import base64
import binascii
import hashlib
import re
import secrets

from app.application.security.refresh import InvalidRefreshTokenError, IssuedRefreshToken

_CANONICAL_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")


class SecureRefreshTokenService:
    def issue(self) -> IssuedRefreshToken:
        secret = secrets.token_bytes(32)
        raw_token = (
            base64.urlsafe_b64encode(secret)
            .decode("ascii")
            .rstrip("=")
        )

        return IssuedRefreshToken(
            raw_token=raw_token,
            token_hash=hashlib.sha256(secret).digest(),
        )

    def digest(self, raw_token: str) -> bytes:
        # Step 1: must be str
        if not isinstance(raw_token, str):
            raise InvalidRefreshTokenError("invalid refresh token")

        # Step 2: must match exactly ^[A-Za-z0-9_-]{43}$
        if not _CANONICAL_RE.fullmatch(raw_token):
            raise InvalidRefreshTokenError("invalid refresh token")

        # Step 3 + 4: decode with exactly the minimal required padding; must be 32 bytes
        try:
            decoded_secret = base64.urlsafe_b64decode(raw_token + "=")
        except binascii.Error as exc:
            raise InvalidRefreshTokenError("invalid refresh token") from exc

        if len(decoded_secret) != 32:
            raise InvalidRefreshTokenError("invalid refresh token")

        # Step 5: re-encode and verify canonical round-trip
        reencoded = base64.urlsafe_b64encode(decoded_secret).decode("ascii").rstrip("=")
        if reencoded != raw_token:
            raise InvalidRefreshTokenError("invalid refresh token")

        # Step 6: return SHA-256 of the decoded secret
        return hashlib.sha256(decoded_secret).digest()
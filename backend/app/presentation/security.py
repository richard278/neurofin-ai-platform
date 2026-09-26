from fastapi import HTTPException, Request, Response, status

from app.core.config import Settings

REFRESH_COOKIE_NAME = "__Host-neurofin_refresh"
CSRF_HEADER_NAME = "X-NeuroFin-CSRF"
CSRF_HEADER_VALUE = "1"


def enforce_browser_auth_request(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if not origin or origin != settings.auth_trusted_origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    csrf = request.headers.get(CSRF_HEADER_NAME)
    if csrf != CSRF_HEADER_VALUE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


def set_refresh_cookie(response: Response, raw_refresh_token: str, max_age: int) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        max_age=max_age,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )

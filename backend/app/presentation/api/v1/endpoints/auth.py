from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.application.security.authentication import AuthenticationError
from app.application.security.refresh import RefreshAuthenticationError
from app.application.security.sessions import (
    LoginSessionService,
    LogoutService,
    RefreshSessionService,
)
from app.core.config import Settings, get_settings
from app.presentation.api.v1.schemas.auth import AccessTokenResponse, LoginRequest
from app.presentation.dependencies import (
    get_login_session_service,
    get_logout_service,
    get_refresh_session_service,
)
from app.presentation.security import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    enforce_browser_auth_request,
    set_refresh_cookie,
)

router = APIRouter(prefix="/auth")


@router.post(
    "/login",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),  # noqa: B008
    login_service: LoginSessionService = Depends(get_login_session_service),  # noqa: B008
) -> AccessTokenResponse:
    enforce_browser_auth_request(request, settings)

    try:
        tokens = await login_service.login(payload.email, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from exc

    now = datetime.now(UTC)
    max_age = max(0, int((tokens.refresh_expires_at - now).total_seconds()))
    set_refresh_cookie(response, tokens.refresh_token, max_age)

    return AccessTokenResponse(
        access_token=tokens.access_token,
        token_type="bearer",
        expires_in=600,
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
)
async def refresh(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),  # noqa: B008
    refresh_service: RefreshSessionService = Depends(get_refresh_session_service),  # noqa: B008
) -> AccessTokenResponse:
    enforce_browser_auth_request(request, settings)

    cookie_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )

    try:
        tokens = await refresh_service.refresh(cookie_token)
    except RefreshAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from exc

    now = datetime.now(UTC)
    max_age = max(0, int((tokens.refresh_expires_at - now).total_seconds()))
    set_refresh_cookie(response, tokens.refresh_token, max_age)

    return AccessTokenResponse(
        access_token=tokens.access_token,
        token_type="bearer",
        expires_in=600,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),  # noqa: B008
    logout_service: LogoutService = Depends(get_logout_service),  # noqa: B008
) -> Response:
    enforce_browser_auth_request(request, settings)

    cookie_token = request.cookies.get(REFRESH_COOKIE_NAME)
    await logout_service.logout(cookie_token)

    response.status_code = status.HTTP_204_NO_CONTENT
    clear_refresh_cookie(response)
    return response

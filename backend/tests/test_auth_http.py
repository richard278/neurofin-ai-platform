from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.application.security.authentication import AuthenticationError
from app.application.security.clock import Clock
from app.application.security.refresh import RefreshAuthenticationError
from app.application.security.sessions import (
    AuthSessionTokens,
    LoginSessionService,
    LogoutService,
    RefreshSessionService,
)
from app.main import app

TRUSTED_ORIGIN = "http://localhost:3000"
CSRF_HEADER = {"X-NeuroFin-CSRF": "1"}


class FakeClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)


class SpyLoginService(LoginSessionService):
    def __init__(self) -> None:
        self.called_with: list[tuple[str, str]] = []
        self.should_fail = False

    async def login(self, email: str, password: str) -> AuthSessionTokens:
        self.called_with.append((email, password))
        if self.should_fail:
            raise AuthenticationError("invalid credentials")

        now = datetime.now(UTC)
        return AuthSessionTokens(
            access_token="fake.access.jwt.token",
            access_expires_at=now + timedelta(seconds=600),
            refresh_token="fake_raw_r1_refresh_token_43chars",
            refresh_expires_at=now + timedelta(minutes=30),
        )


class SpyRefreshService(RefreshSessionService):
    def __init__(self) -> None:
        self.called_with: list[str] = []
        self.should_fail = False

    async def refresh(self, raw_refresh_token: str) -> AuthSessionTokens:
        self.called_with.append(raw_refresh_token)
        if self.should_fail:
            raise RefreshAuthenticationError("refresh authentication failed")

        now = datetime.now(UTC)
        return AuthSessionTokens(
            access_token="fake.access.jwt.token.r2",
            access_expires_at=now + timedelta(seconds=600),
            refresh_token="fake_raw_r2_refresh_token_43chars",
            refresh_expires_at=now + timedelta(minutes=30),
        )


class SpyLogoutService(LogoutService):
    def __init__(self) -> None:
        self.called_with: list[str | None] = []

    async def logout(self, raw_refresh_token: str | None) -> None:
        self.called_with.append(raw_refresh_token)


@pytest.fixture
def auth_app() -> tuple[FastAPI, SpyLoginService, SpyRefreshService, SpyLogoutService]:
    login_spy = SpyLoginService()
    refresh_spy = SpyRefreshService()
    logout_spy = SpyLogoutService()

    app.state.login_session_service = login_spy
    app.state.refresh_session_service = refresh_spy
    app.state.logout_service = logout_spy

    return app, login_spy, refresh_spy, logout_spy


@pytest.fixture
def client(auth_app: tuple[FastAPI, Any, Any, Any]) -> TestClient:
    test_app, _, _, _ = auth_app
    return TestClient(test_app, base_url="https://neurofin.example")


# -----------------------------------------------------------------------------
# Transport Security Matrix (Origin + CSRF Header Enforcements)
# -----------------------------------------------------------------------------


def test_login_trusted_origin_and_csrf_header_allowed(
    client: TestClient, auth_app: tuple[FastAPI, SpyLoginService, Any, Any]
) -> None:
    _, login_spy, _, _ = auth_app
    headers = {"Origin": TRUSTED_ORIGIN, **CSRF_HEADER}
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "securepassword123"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_200_OK
    assert len(login_spy.called_with) == 1


def test_wrong_origin_rejected_with_403(
    client: TestClient, auth_app: tuple[FastAPI, SpyLoginService, Any, Any]
) -> None:
    _, login_spy, _, _ = auth_app
    headers = {"Origin": "http://attacker.example", **CSRF_HEADER}
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert len(login_spy.called_with) == 0


def test_lookalike_origin_rejected_with_403(
    client: TestClient, auth_app: tuple[FastAPI, SpyLoginService, Any, Any]
) -> None:
    _, login_spy, _, _ = auth_app
    headers = {"Origin": "http://localhost:3000.attacker.com", **CSRF_HEADER}
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert len(login_spy.called_with) == 0


def test_null_origin_rejected_with_403(
    client: TestClient, auth_app: tuple[FastAPI, SpyLoginService, Any, Any]
) -> None:
    _, login_spy, _, _ = auth_app
    headers = {"Origin": "null", **CSRF_HEADER}
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert len(login_spy.called_with) == 0


def test_missing_origin_rejected_with_403(
    client: TestClient, auth_app: tuple[FastAPI, SpyLoginService, Any, Any]
) -> None:
    _, login_spy, _, _ = auth_app
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password"},
        headers=CSRF_HEADER,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert len(login_spy.called_with) == 0


def test_missing_csrf_header_rejected_with_403(
    client: TestClient, auth_app: tuple[FastAPI, SpyLoginService, Any, Any]
) -> None:
    _, login_spy, _, _ = auth_app
    headers = {"Origin": TRUSTED_ORIGIN}
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert len(login_spy.called_with) == 0


def test_wrong_csrf_value_rejected_with_403(
    client: TestClient, auth_app: tuple[FastAPI, SpyLoginService, Any, Any]
) -> None:
    _, login_spy, _, _ = auth_app
    headers = {"Origin": TRUSTED_ORIGIN, "X-NeuroFin-CSRF": "2"}
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert len(login_spy.called_with) == 0


# -----------------------------------------------------------------------------
# Login Endpoint Behavior
# -----------------------------------------------------------------------------


def test_login_success_returns_access_token_json_only(client: TestClient) -> None:
    headers = {"Origin": TRUSTED_ORIGIN, **CSRF_HEADER}
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "securepassword123"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body == {
        "access_token": "fake.access.jwt.token",
        "token_type": "bearer",
        "expires_in": 600,
    }
    assert "refresh_token" not in body


def test_login_success_writes_secure_refresh_cookie(client: TestClient) -> None:
    headers = {"Origin": TRUSTED_ORIGIN, **CSRF_HEADER}
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "securepassword123"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_200_OK
    set_cookie_header = res.headers.get("set-cookie", "")
    assert "__Host-neurofin_refresh=fake_raw_r1_refresh_token_43chars" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "Secure" in set_cookie_header
    assert "samesite=strict" in set_cookie_header.lower()
    assert "path=/" in set_cookie_header.lower()
    assert "domain=" not in set_cookie_header.lower()


def test_login_failure_returns_generic_401(
    client: TestClient, auth_app: tuple[FastAPI, SpyLoginService, Any, Any]
) -> None:
    _, login_spy, _, _ = auth_app
    login_spy.should_fail = True
    headers = {"Origin": TRUSTED_ORIGIN, **CSRF_HEADER}
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "wrongpassword"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "set-cookie" not in res.headers


# -----------------------------------------------------------------------------
# Refresh Endpoint Behavior
# -----------------------------------------------------------------------------


def test_refresh_reads_cookie_and_returns_access_token_and_rotated_cookie(
    client: TestClient, auth_app: tuple[FastAPI, Any, SpyRefreshService, Any]
) -> None:
    _, _, refresh_spy, _ = auth_app
    headers = {"Origin": TRUSTED_ORIGIN, **CSRF_HEADER}
    client.cookies.set("__Host-neurofin_refresh", "fake_raw_r1_refresh_token_43chars")

    res = client.post("/api/v1/auth/refresh", headers=headers)

    assert res.status_code == status.HTTP_200_OK
    assert refresh_spy.called_with == ["fake_raw_r1_refresh_token_43chars"]
    body = res.json()
    assert body == {
        "access_token": "fake.access.jwt.token.r2",
        "token_type": "bearer",
        "expires_in": 600,
    }
    assert "refresh_token" not in body

    set_cookie_header = res.headers.get("set-cookie", "")
    assert "__Host-neurofin_refresh=fake_raw_r2_refresh_token_43chars" in set_cookie_header


def test_refresh_failed_returns_generic_401(
    client: TestClient, auth_app: tuple[FastAPI, Any, SpyRefreshService, Any]
) -> None:
    _, _, refresh_spy, _ = auth_app
    refresh_spy.should_fail = True
    headers = {"Origin": TRUSTED_ORIGIN, **CSRF_HEADER}
    client.cookies.set("__Host-neurofin_refresh", "invalid_refresh_token")

    res = client.post("/api/v1/auth/refresh", headers=headers)

    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_requires_no_access_jwt(client: TestClient) -> None:
    headers = {"Origin": TRUSTED_ORIGIN, **CSRF_HEADER}
    client.cookies.set("__Host-neurofin_refresh", "fake_raw_r1_refresh_token_43chars")

    # Call refresh without Authorization header
    res = client.post("/api/v1/auth/refresh", headers=headers)
    assert res.status_code == status.HTTP_200_OK


# -----------------------------------------------------------------------------
# Logout Endpoint Behavior
# -----------------------------------------------------------------------------


def test_logout_returns_204_and_clears_cookie(
    client: TestClient, auth_app: tuple[FastAPI, Any, Any, SpyLogoutService]
) -> None:
    _, _, _, logout_spy = auth_app
    headers = {"Origin": TRUSTED_ORIGIN, **CSRF_HEADER}
    client.cookies.set("__Host-neurofin_refresh", "fake_raw_r1_refresh_token_43chars")

    res = client.post("/api/v1/auth/logout", headers=headers)

    assert res.status_code == status.HTTP_204_NO_CONTENT
    assert logout_spy.called_with == ["fake_raw_r1_refresh_token_43chars"]

    set_cookie_header = res.headers.get("set-cookie", "")
    assert "__Host-neurofin_refresh=" in set_cookie_header
    assert "max-age=0" in set_cookie_header.lower() or "expires=" in set_cookie_header.lower()


def test_logout_missing_cookie_still_returns_204_and_clears_cookie(
    client: TestClient, auth_app: tuple[FastAPI, Any, Any, SpyLogoutService]
) -> None:
    _, _, _, logout_spy = auth_app
    headers = {"Origin": TRUSTED_ORIGIN, **CSRF_HEADER}

    res = client.post("/api/v1/auth/logout", headers=headers)

    assert res.status_code == status.HTTP_204_NO_CONTENT
    assert logout_spy.called_with == [None]

    set_cookie_header = res.headers.get("set-cookie", "")
    assert "__Host-neurofin_refresh=" in set_cookie_header


def test_logout_requires_no_access_jwt(client: TestClient) -> None:
    headers = {"Origin": TRUSTED_ORIGIN, **CSRF_HEADER}
    res = client.post("/api/v1/auth/logout", headers=headers)
    assert res.status_code == status.HTTP_204_NO_CONTENT


def test_logout_unknown_cookie_still_returns_204_and_clears_cookie(
    client: TestClient, auth_app: tuple[FastAPI, Any, Any, SpyLogoutService]
) -> None:
    _, _, _, logout_spy = auth_app
    headers = {"Origin": TRUSTED_ORIGIN, **CSRF_HEADER}
    client.cookies.set("__Host-neurofin_refresh", "fake_raw_unknown_refresh_token_43chars")

    res = client.post("/api/v1/auth/logout", headers=headers)

    assert res.status_code == status.HTTP_204_NO_CONTENT
    assert logout_spy.called_with == ["fake_raw_unknown_refresh_token_43chars"]

    set_cookie_header = res.headers.get("set-cookie", "")
    assert "__Host-neurofin_refresh=" in set_cookie_header
    assert "max-age=0" in set_cookie_header.lower() or "expires=" in set_cookie_header.lower()
    assert "httponly" in set_cookie_header.lower()
    assert "secure" in set_cookie_header.lower()
    assert "samesite=strict" in set_cookie_header.lower()
    assert "path=/" in set_cookie_header.lower()
    assert "domain=" not in set_cookie_header.lower()

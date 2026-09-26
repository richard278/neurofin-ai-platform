from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .presentation.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None, None]:
    settings_obj = get_settings()
    engine = None
    if settings_obj.database_url:
        from .infrastructure.database.engine import create_database_engine
        from .infrastructure.database.session import create_session_factory
        from .infrastructure.security.argon2_password_hasher import (
            Argon2idPasswordHasher,
        )
        from .infrastructure.security.jwt_access_token_service import (
            JWTAccessTokenService,
        )
        from .infrastructure.security.key_loader import load_pem
        from .infrastructure.security.refresh_token_service import (
            SecureRefreshTokenService,
        )
        from .infrastructure.security.sqlalchemy_login_session_service import (
            SQLAlchemyLoginSessionService,
        )
        from .infrastructure.security.sqlalchemy_logout_service import (
            SQLAlchemyLogoutService,
        )
        from .infrastructure.security.sqlalchemy_refresh_session_service import (
            SQLAlchemyRefreshSessionService,
        )
        from .infrastructure.security.system_clock import SystemClock

        engine = create_database_engine(settings_obj)
        session_factory = create_session_factory(engine)
        clock = SystemClock()
        hasher = Argon2idPasswordHasher(settings_obj)
        refresh_token_svc = SecureRefreshTokenService()

        private_key_pem = load_pem(
            settings_obj.jwt_private_key_path, "JWT private key"
        )
        public_key_pem = load_pem(
            settings_obj.jwt_public_key_path, "JWT public key"
        )
        access_token_svc = JWTAccessTokenService(
            private_key_pem=private_key_pem,
            public_key_pem=public_key_pem,
            clock=clock,
        )

        app_instance.state.login_session_service = SQLAlchemyLoginSessionService(
            session_factory=session_factory,
            password_hasher=hasher,
            refresh_token_service=refresh_token_svc,
            access_token_service=access_token_svc,
            clock=clock,
            dummy_password_hash=settings_obj.auth_dummy_password_hash,
        )
        app_instance.state.refresh_session_service = SQLAlchemyRefreshSessionService(
            session_factory=session_factory,
            refresh_token_service=refresh_token_svc,
            access_token_service=access_token_svc,
            clock=clock,
        )
        app_instance.state.logout_service = SQLAlchemyLogoutService(
            session_factory=session_factory,
            refresh_token_service=refresh_token_svc,
            clock=clock,
        )

    yield

    if engine:
        await engine.dispose()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-NeuroFin-CSRF",
    ],
)

app.include_router(api_router, prefix=settings.api_prefix)

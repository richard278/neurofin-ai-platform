# NF-AUTH-03 Secure Authentication & Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and independently verify NeuroFin's secure credential authentication, short-lived PS256 access JWTs, stateful PostgreSQL refresh sessions, atomic single-use refresh rotation, replay/reuse family revocation, logout, and browser transport without introducing provisioning, business authorization, MFA, OAuth/OIDC, or unrelated product scope.

**Architecture:** Preserve Clean Architecture by keeping identity in Domain, authentication/session contracts and pure orchestration models in Application/Security, cryptographic and SQLAlchemy implementations in Infrastructure, and HTTP/cookie/CORS behavior in Presentation. Access JWTs remain stateless and short-lived; refresh state is PostgreSQL-backed, hash-only, locked and rotated transactionally. Every PostgreSQL-dependent property is proved on real PostgreSQL, and every microiteration ends at a mandatory architectural STOP.

**Tech Stack:** Python 3.11, FastAPI, Pydantic Settings, `argon2-cffi` 25.1.x, PyJWT 2.13.x with cryptography support, SQLAlchemy 2.0.x async, asyncpg 0.31.x, Alembic 1.19.x, PostgreSQL 18.4, pytest/pytest-asyncio/httpx, Ruff, mypy, React 18, TypeScript 5, Vite 5.

**Spec:** `docs/superpowers/specs/2026-08-29-nf-auth-03-secure-authentication-session-design.md`

## Global Constraints

- Published functional baseline before documentation: `090de6c61c6f8d731df0ab24f13b73e788b28a3c`.
- Governing security baseline: `24e418edb84c94d816a40b3b8f05ef1c20ef87cb`.
- Python runtime remains `>=3.11`; Ruff target remains `py311`; mypy Python remains `3.11`.
- PostgreSQL is authoritative for schema, constraints, transactions, rollback, locking, concurrency, reuse detection, and revocation evidence. SQLite is not a substitute for those properties.
- SQLAlchemy remains `>=2.0.52,<2.1.0`; asyncpg remains `>=0.31.0,<1.0.0`; Alembic remains `>=1.19.0,<2.0.0`.
- Add `argon2-cffi>=25.1.0,<26.0.0` only in `03-A`.
- Add `PyJWT[crypto]>=2.13.0,<3.0.0` only in `03-C`.
- Domain must not import FastAPI, Pydantic, SQLAlchemy, asyncpg, PostgreSQL, JWT libraries, Argon2 libraries, cookie APIs, or CORS APIs.
- Application/Security must not import FastAPI, SQLAlchemy, `AsyncSession`, asyncpg, PostgreSQL, cookie APIs, or CORS middleware.
- `Domain.User` remains `UUID + canonical email + UserRole(ANALYST|ADMIN)`; no password field is added.
- `SEC-Q02` provisioning remains open. No signup, registration, invite, ADMIN-create-user endpoint, demo provisioning, password reset, password recovery, or password-change endpoint is added.
- New password credentials use Argon2id. Plaintext password persistence/logging is zero.
- Candidate Argon2id implementation parameters for the first benchmark are explicit and versioned: `memory_cost=65536 KiB`, `time_cost=3`, `parallelism=4`, `hash_len=32`, `salt_len=16`. These match the current argon2-cffi RFC 9106 low-memory profile candidate and must be measured in `03-A`; Gate A may reject them without silently changing them.
- Dummy password verification uses a controlled non-secret valid PHC and is never generated per request.
- Access JWT algorithm is exactly `PS256`; header `typ` is exactly `neurofin-access+jwt`.
- Mandatory access claims are exactly `sub`, `iss`, `aud`, `iat`, `exp`, `jti`, `role`.
- `iss = urn:neurofin:auth`; `aud = urn:neurofin:api`.
- Access JWT nominal TTL is 10 minutes; validation leeway is at most 30 seconds.
- `jti` is a new UUIDv4 per access JWT, not persisted, and not used for a denylist.
- Every newly issued access JWT reloads authoritative `User.role`; already-issued JWTs remain stateless snapshots.
- Refresh generation TTL is 30 minutes; refresh clock leeway/grace is zero.
- Refresh session absolute TTL is 8 hours and non-sliding.
- Security time comes from a server-side timezone-aware UTC `Clock`.
- Each refresh secret is 32 independent CSPRNG bytes encoded as canonical unpadded 43-character Base64URL.
- Refresh persistence stores only `SHA-256(decoded_secret)` as a 32-byte binary digest.
- Raw refresh secrets never enter PostgreSQL, logs, audit payloads, metrics, traces, or JSON responses.
- Refresh lock order is always `refresh_session -> refresh_token`.
- Refresh rotation uses PostgreSQL `SELECT ... FOR UPDATE`, revalidates after locking, and creates at most one successor.
- Consumed refresh reuse in an active family revokes the family; no grace/idempotent consumed-token retry exists.
- A reuse-triggered family revocation must commit before the outward rejection is raised.
- Logout revokes only the current refresh family and is externally idempotent.
- Existing access JWTs are not denylisted on logout and may remain valid until temporal validation fails.
- Browser refresh cookie is exactly `__Host-neurofin_refresh`, `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`, with no `Domain`.
- Browser login/refresh/logout require exact trusted `Origin` and `X-NeuroFin-CSRF: 1`.
- Production target is same-origin. Development CORS is explicit; wildcard origins/methods/headers are not the final auth posture.
- Access JWT is response-body data and frontend runtime-memory only; never localStorage/sessionStorage/IndexedDB/persistent cookie.
- The existing API prefix is configuration-driven and currently defaults to `/api/v1`; auth suffixes are `/auth/login`, `/auth/refresh`, `/auth/logout`.
- No `/auth/me` is added by this phase.
- Repositories may `flush()` but may not own `commit()`, `rollback()`, or session lifecycle.
- Opportunistic rehash is post-authentication and post-core-session-commit. Rehash failure does not invalidate a valid login.
- Rehash uses compare-and-replace: `user_id + expected_hash -> replacement_hash`; concurrent credential change returns no-op rather than overwrite.
- Known baseline Ruff/mypy debt may remain; new debt attributable to NF-AUTH-03 must be zero.
- Security-critical failure at any Gate is NO-GO; there is no compensation by unrelated green tests.
- Every microiteration ends with a mandatory STOP. Approval of one microiteration does not authorize the next.
- Use TDD: demonstrate RED before minimal implementation and GREEN afterward.
- No force push, hidden stash/reset/clean, or silent scope repair is permitted.
- Exact `AC-NF-SEC-*` identifiers must be read from the canonical `NF-SEC-00-E` matrix during `03-I`; do not guess or renumber them.

---

## File Structure Map

The map below locks intended responsibilities. Exact file creation occurs only in the microiteration that owns it.

### Existing files expected to be modified

- `backend/pyproject.toml` — add Argon2 dependency in `03-A`, then PyJWT crypto dependency in `03-C`.
- `backend/app/core/config.py` — Argon2 candidate parameters/dummy PHC in `03-A`; auth origin/key-path settings in `03-H`.
- `backend/app/domain/entities/user.py` — expose the already-existing canonical email rule as a public function in `03-C` without changing identity semantics.
- `backend/app/infrastructure/database/models/__init__.py` — export credential model in `03-B`, refresh models in `03-D`.
- `backend/alembic/env.py` — register credential model in `03-B`, refresh models in `03-D`.
- `backend/tests/test_alembic_foundation.py` — update current-head assertions as migrations advance.
- `backend/app/presentation/api/v1/router.py` — include auth router in `03-H`.
- `backend/app/presentation/dependencies.py` — add auth/runtime composition helpers in `03-H` without changing forecast behavior.
- `backend/app/main.py` — lifecycle/database auth composition and restrictive CORS in `03-H`.
- `frontend/src/api/client.ts` — support optional Bearer header while preserving generic request behavior in `03-H`.

### New Application/Security files

- `backend/app/application/security/__init__.py` — package marker.
- `backend/app/application/security/passwords.py` — `PasswordHasher` port and controlled hash errors.
- `backend/app/application/security/credentials.py` — `PasswordCredential`, credential repository port, repository errors.
- `backend/app/application/security/clock.py` — timezone-aware UTC `Clock` port.
- `backend/app/application/security/tokens.py` — access-token port, claims/principal/result types and token errors.
- `backend/app/application/security/authentication.py` — non-enumerating credential authentication and optional rehash candidate.
- `backend/app/application/security/refresh.py` — refresh records, repository port, refresh-token service port and generic refresh error.
- `backend/app/application/security/sessions.py` — login/refresh/logout service protocols and `AuthSessionTokens`.

### New Infrastructure/Security files

- `backend/app/infrastructure/security/__init__.py` — package marker.
- `backend/app/infrastructure/security/argon2_password_hasher.py` — Argon2id adapter.
- `backend/app/infrastructure/security/system_clock.py` — UTC system clock.
- `backend/app/infrastructure/security/jwt_access_token_service.py` — PS256 issuer/validator.
- `backend/app/infrastructure/security/refresh_token_service.py` — CSPRNG/Base64URL/SHA-256 implementation.
- `backend/app/infrastructure/security/key_loader.py` — PEM file loading with no logging.
- `backend/app/infrastructure/security/sqlalchemy_login_session_service.py` — login/session durability plus post-commit rehash.
- `backend/app/infrastructure/security/sqlalchemy_refresh_session_service.py` — locked rotation/reuse state machine.
- `backend/app/infrastructure/security/sqlalchemy_logout_service.py` — current-family logout/revocation.

### New database/mapping/repository files

- `backend/app/infrastructure/database/models/user_credential.py` — 1:1 `user_credentials` ORM model.
- `backend/app/infrastructure/database/mappers/credential_mapper.py` — pure credential mapping.
- `backend/app/infrastructure/repositories/sqlalchemy_credential_repository.py` — credential adapter, flush-only, compare-and-replace.
- `backend/app/infrastructure/database/models/refresh.py` — `RefreshSessionModel` and `RefreshTokenModel`.
- `backend/app/infrastructure/database/mappers/refresh_mapper.py` — pure refresh record mapping.
- `backend/app/infrastructure/repositories/sqlalchemy_refresh_repository.py` — refresh lookup/lock/mutation adapter, no transaction ownership.

### New Alembic revisions

- `backend/alembic/versions/20260829a001_create_user_credentials.py` — `down_revision = "20260824a001"`.
- `backend/alembic/versions/20260829a002_create_refresh_sessions.py` — `down_revision = "20260829a001"`.

### New Presentation files

- `backend/app/presentation/api/v1/schemas/auth.py` — login request and access-token response schemas.
- `backend/app/presentation/api/v1/endpoints/auth.py` — login/refresh/logout HTTP surface.
- `backend/app/presentation/security.py` — exact Origin/CSRF checks and refresh-cookie helpers.

### New frontend transport file

- `frontend/src/api/auth.ts` — runtime-memory access token, credentialed login/refresh/logout, CSRF header.

### New tests/evidence files

- `backend/tests/test_password_security.py`
- `backend/tests/test_credential_orm_repository.py`
- `backend/tests/test_authentication_core.py`
- `backend/tests/test_jwt_access_token.py`
- `backend/tests/test_refresh_crypto.py`
- `backend/tests/test_refresh_orm_repository.py`
- `backend/tests/test_login_session_service.py`
- `backend/tests/test_refresh_session_service.py`
- `backend/tests/test_logout_service.py`
- `backend/tests/test_auth_http.py`
- `backend/tests/integration/test_credential_postgres.py`
- `backend/tests/integration/test_refresh_schema_postgres.py`
- `backend/tests/integration/test_login_session_postgres.py`
- `backend/tests/integration/test_refresh_rotation_postgres.py`
- `backend/tests/integration/test_logout_postgres.py`
- `backend/tests/integration/test_auth_security_postgres.py`
- `backend/scripts/benchmark_argon2.py`
- generated evidence: `backend/docs/superpowers/evidence/2026-08-29-nf-auth-03-a-argon2-benchmark.json`
- integrated evidence index: `backend/docs/superpowers/evidence/2026-08-29-nf-auth-03-security-evidence-index.md`

No business forecast model, ownership model, authorization policy, provisioning endpoint, MFA/OAuth component, or ML persistence path is planned.

---

## Pre-Execution Documentation Gate

The approved specification and this plan must be placed and versioned before source implementation begins.

Expected repository paths:

```text
backend/docs/superpowers/specs/2026-08-29-nf-auth-03-secure-authentication-session-design.md
backend/docs/superpowers/plans/2026-08-29-nf-auth-03-secure-authentication-session-implementation-plan.md
```

- [ ] **Step DG-1: Verify the published input baseline**

From repository root:

```bash
git remote -v
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git status --short --untracked-files=all
```

Required before placing the two documents:

```text
repository = richard278/neurofin-ai-platform
branch = main
HEAD = 090de6c61c6f8d731df0ab24f13b73e788b28a3c
origin/main = 090de6c61c6f8d731df0ab24f13b73e788b28a3c
working tree = CLEAN
```

If any value differs, STOP. Do not reset, restore, stash, clean, or force the repository.

- [ ] **Step DG-2: Place the approved spec and this plan at the exact paths**

Do not edit content while copying.

- [ ] **Step DG-3: Verify documentation-only scope**

```bash
git status --short --untracked-files=all
git diff --check
git diff --stat
```

Expected only the two new documentation paths.

- [ ] **Step DG-4: Version the approved specification first**

```bash
git add backend/docs/superpowers/specs/2026-08-29-nf-auth-03-secure-authentication-session-design.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: add NF-AUTH-03 secure authentication design"
```

Expected staged path cardinality before commit: exactly 1.

- [ ] **Step DG-5: Version the implementation plan second**

```bash
git add backend/docs/superpowers/plans/2026-08-29-nf-auth-03-secure-authentication-session-implementation-plan.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: add NF-AUTH-03 implementation plan"
```

Expected staged path cardinality before commit: exactly 1.

- [ ] **Step DG-6: Verify the documentation baseline**

```bash
git status --short
git log -2 --oneline
git show --name-only --format="" HEAD
git diff HEAD~2..HEAD --name-only
```

Expected: clean tree and exactly the spec + plan across the two documentation commits.

- [ ] **Step DG-7: Controlled push after architectural confirmation**

```bash
git push origin main
git rev-parse HEAD
git rev-parse origin/main
git status --short
```

Required: `HEAD == origin/main`, working tree clean.

- [ ] **Step DG-8: STOP**

Do not begin `03-A` until the Documentation Gate is explicitly accepted.

---

### Task 1: NF-AUTH-03-A — Credential Contracts + Argon2id + Benchmark

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Create: `backend/app/application/security/__init__.py`
- Create: `backend/app/application/security/passwords.py`
- Create: `backend/app/application/security/credentials.py`
- Create: `backend/app/infrastructure/security/__init__.py`
- Create: `backend/app/infrastructure/security/argon2_password_hasher.py`
- Create: `backend/scripts/benchmark_argon2.py`
- Create: `backend/tests/test_password_security.py`
- Generate: `backend/docs/superpowers/evidence/2026-08-29-nf-auth-03-a-argon2-benchmark.json`

**Interfaces:**
- Produces:
  - `PasswordCredential(user_id: UUID, password_hash: str)`.
  - `PasswordHasher.hash(password: str) -> str`.
  - `PasswordHasher.verify(password: str, encoded_hash: str) -> bool`.
  - `PasswordHasher.needs_rehash(encoded_hash: str) -> bool`.
  - `PasswordHashError`.
  - `CredentialRepository.add/get_by_user_id/replace_hash`.
  - `CredentialRepositoryError`, `CredentialAlreadyExistsError`.
  - `Argon2idPasswordHasher`.
- Consumes: stdlib in Application; `argon2-cffi` only in Infrastructure.

- [ ] **Step 1.1: Add the Argon2 dependency and explicit candidate configuration tests first**

Add to `backend/tests/test_password_security.py`:

```python
from uuid import uuid4

import pytest

from app.application.security.credentials import (
    CredentialAlreadyExistsError,
    CredentialRepositoryError,
    PasswordCredential,
)
from app.application.security.passwords import PasswordHashError, PasswordHasher
from app.core.config import Settings
from app.infrastructure.security.argon2_password_hasher import Argon2idPasswordHasher


def test_argon2_candidate_settings_are_explicit() -> None:
    settings = Settings(_env_file=None)

    assert settings.argon2_memory_cost_kib == 65536
    assert settings.argon2_time_cost == 3
    assert settings.argon2_parallelism == 4
    assert settings.argon2_hash_len == 32
    assert settings.argon2_salt_len == 16
    assert settings.auth_dummy_password_hash.startswith("$argon2id$")


def test_password_credential_is_opaque_application_data() -> None:
    credential = PasswordCredential(user_id=uuid4(), password_hash="$argon2id$opaque")

    assert credential.password_hash == "$argon2id$opaque"
    assert issubclass(CredentialAlreadyExistsError, CredentialRepositoryError)


def test_password_hasher_is_an_application_port() -> None:
    assert PasswordHasher.__module__ == "app.application.security.passwords"
```

Run:

```bash
cd backend
source .venv/Scripts/activate
python -m pytest tests/test_password_security.py -v
```

Expected RED: imports/fields do not exist yet.

- [ ] **Step 1.2: Add the dependency only**

In `backend/pyproject.toml`, add inside runtime dependencies:

```toml
"argon2-cffi>=25.1.0,<26.0.0",
```

Install from the canonical project metadata:

```bash
python -m pip install -e ".[dev]"
python -m pip check
```

Expected: install succeeds and `pip check` reports no broken requirements.

- [ ] **Step 1.3: Add candidate Argon2 configuration and the controlled dummy PHC**

Add these `Settings` fields in `backend/app/core/config.py`:

```python
argon2_memory_cost_kib: int = 65536
argon2_time_cost: int = 3
argon2_parallelism: int = 4
argon2_hash_len: int = 32
argon2_salt_len: int = 16
auth_dummy_password_hash: str = (
    "$argon2id$v=19$m=65536,t=3,p=4$Fl1Grf6vpX5SKg0514uA/w$"
    "B1b6Q8zwVQTD9GWQzzk6qXlmaYCjPcfUXI1rbfTDKRo"
)
```

The dummy PHC is non-secret and exists solely to make the unknown-user path perform Argon2 verification. It is not a user credential.

- [ ] **Step 1.4: Implement Application credential/password contracts**

Create `backend/app/application/security/passwords.py`:

```python
from typing import Protocol


class PasswordHashError(RuntimeError):
    pass


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        ...

    def verify(self, password: str, encoded_hash: str) -> bool:
        ...

    def needs_rehash(self, encoded_hash: str) -> bool:
        ...
```

Create `backend/app/application/security/credentials.py`:

```python
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class CredentialRepositoryError(RuntimeError):
    pass


class CredentialAlreadyExistsError(CredentialRepositoryError):
    pass


@dataclass(frozen=True)
class PasswordCredential:
    user_id: UUID
    password_hash: str


class CredentialRepository(Protocol):
    async def add(self, credential: PasswordCredential) -> None:
        ...

    async def get_by_user_id(self, user_id: UUID) -> PasswordCredential | None:
        ...

    async def replace_hash(
        self,
        user_id: UUID,
        expected_hash: str,
        replacement_hash: str,
    ) -> bool:
        ...
```

Create package marker files as empty files.

- [ ] **Step 1.5: Implement the Argon2id adapter**

Create `backend/app/infrastructure/security/argon2_password_hasher.py`:

```python
from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import (
    HashingError,
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from argon2.low_level import Type

from app.application.security.passwords import PasswordHashError
from app.core.config import Settings


class Argon2idPasswordHasher:
    def __init__(self, settings: Settings) -> None:
        self._hasher = Argon2PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost_kib,
            parallelism=settings.argon2_parallelism,
            hash_len=settings.argon2_hash_len,
            salt_len=settings.argon2_salt_len,
            type=Type.ID,
        )

    def hash(self, password: str) -> str:
        try:
            return self._hasher.hash(password)
        except HashingError as exc:
            raise PasswordHashError("password hashing failed") from exc

    def verify(self, password: str, encoded_hash: str) -> bool:
        try:
            return self._hasher.verify(encoded_hash, password)
        except VerifyMismatchError:
            return False
        except (InvalidHashError, VerificationError) as exc:
            raise PasswordHashError("password verification failed") from exc

    def needs_rehash(self, encoded_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(encoded_hash)
        except (InvalidHashError, VerificationError) as exc:
            raise PasswordHashError("password hash inspection failed") from exc
```

Do not log password or PHC values.

- [ ] **Step 1.6: Complete the Argon2 contract tests**

Append:

```python
def make_hasher() -> Argon2idPasswordHasher:
    return Argon2idPasswordHasher(Settings(_env_file=None))


def test_argon2id_hash_verify_and_salt_variation() -> None:
    hasher = make_hasher()

    first = hasher.hash("correct horse battery staple")
    second = hasher.hash("correct horse battery staple")

    assert first.startswith("$argon2id$")
    assert second.startswith("$argon2id$")
    assert first != second
    assert hasher.verify("correct horse battery staple", first) is True
    assert hasher.verify("wrong password", first) is False
    assert hasher.needs_rehash(first) is False


def test_argon2id_malformed_hash_fails_closed() -> None:
    hasher = make_hasher()

    with pytest.raises(PasswordHashError):
        hasher.verify("secret", "not-a-phc")

    with pytest.raises(PasswordHashError):
        hasher.needs_rehash("not-a-phc")
```

Run:

```bash
python -m pytest tests/test_password_security.py -v
```

Expected GREEN.

- [ ] **Step 1.7: Implement deterministic benchmark evidence generation**

Create `backend/scripts/benchmark_argon2.py`:

```python
import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

from app.core.config import Settings
from app.infrastructure.security.argon2_password_hasher import Argon2idPasswordHasher


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.samples < 5:
        raise ValueError("samples must be >= 5")

    settings = Settings(_env_file=None)
    hasher = Argon2idPasswordHasher(settings)
    password = "neurofin-argon2-benchmark-input"
    encoded = hasher.hash(password)

    timings_ms: list[float] = []
    for _ in range(args.samples):
        started = time.perf_counter()
        verified = hasher.verify(password, encoded)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if not verified:
            raise RuntimeError("benchmark verification failed")
        timings_ms.append(elapsed_ms)

    ordered = sorted(timings_ms)
    p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95))

    evidence = {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "algorithm": "Argon2id",
        "memory_cost_kib": settings.argon2_memory_cost_kib,
        "time_cost": settings.argon2_time_cost,
        "parallelism": settings.argon2_parallelism,
        "hash_len": settings.argon2_hash_len,
        "salt_len": settings.argon2_salt_len,
        "samples": args.samples,
        "median_verify_ms": round(statistics.median(timings_ms), 3),
        "p95_verify_ms": round(ordered[p95_index], 3),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```bash
python scripts/benchmark_argon2.py \
  --samples 20 \
  --output docs/superpowers/evidence/2026-08-29-nf-auth-03-a-argon2-benchmark.json
```

Expected:
- command exit 0;
- JSON contains environment, parameters, sample count, median and p95;
- no plaintext user password, raw credential, or secret is present.

The Gate reviewer must judge the measured latency before accepting the candidate parameters. Do not silently retune them during the same Gate.

- [ ] **Step 1.8: Run focused and regression verification**

```bash
python -m pytest tests/test_password_security.py -v
python -m pytest -q
python -m ruff check \
  app/application/security \
  app/infrastructure/security/argon2_password_hasher.py \
  tests/test_password_security.py \
  scripts/benchmark_argon2.py
python -m mypy \
  app/application/security \
  app/infrastructure/security/argon2_password_hasher.py
python -m pip check
git diff --check
git status --short --untracked-files=all
```

Required:
- focused tests PASS;
- regression has 0 failures;
- focused Ruff/mypy PASS;
- pip check PASS;
- no unplanned path.

- [ ] **Step 1.9: STOP for Gate `03-A`**

Gate evidence must include the benchmark JSON. No staging/commit until review.

- [ ] **Step 1.10: After Gate approval, commit/push only `03-A`**

Suggested commit:

```bash
git commit -m "feat: add Argon2id credential security core"
```

After controlled push, prove `HEAD == origin/main`, clean tree, then STOP again before `03-B`.

---

### Task 2: NF-AUTH-03-B — Credential ORM + Alembic + Repository

**Files:**
- Create: `backend/app/infrastructure/database/models/user_credential.py`
- Modify: `backend/app/infrastructure/database/models/__init__.py`
- Create: `backend/app/infrastructure/database/mappers/credential_mapper.py`
- Create: `backend/app/infrastructure/repositories/sqlalchemy_credential_repository.py`
- Modify: `backend/alembic/env.py`
- Modify: `backend/tests/test_alembic_foundation.py`
- Create: `backend/alembic/versions/20260829a001_create_user_credentials.py`
- Create: `backend/tests/test_credential_orm_repository.py`
- Create: `backend/tests/integration/test_credential_postgres.py`

**Interfaces:**
- Consumes: `PasswordCredential`, `CredentialRepository`, `CredentialRepositoryError`, `CredentialAlreadyExistsError`.
- Produces: `UserCredentialModel`; migration head `20260829a001`; `SQLAlchemyCredentialRepository`.
- Repository owns `flush()` only; external caller owns transaction/session lifecycle.

- [ ] **Step 2.1: Docker/PostgreSQL preflight before any mutation**

Before editing:

```bash
docker info
docker compose version
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git status --short --untracked-files=all
```

If Docker Engine is unavailable, STOP as `ENVIRONMENT / DOCKER NOT READY`. Do not edit code or retry in a loop.

Start only the project-approved disposable PostgreSQL integration stack and wait for health `healthy`.

- [ ] **Step 2.2: Write ORM/repository tests first**

Create `backend/tests/test_credential_orm_repository.py` with structural assertions:

```python
from uuid import uuid4

from sqlalchemy import inspect

from app.application.security.credentials import PasswordCredential
from app.infrastructure.database.mappers.credential_mapper import (
    credential_to_model,
    model_to_credential,
)
from app.infrastructure.database.models.user_credential import UserCredentialModel


def test_user_credentials_metadata_contract() -> None:
    table = UserCredentialModel.__table__

    assert table.name == "user_credentials"
    assert set(table.columns.keys()) == {"user_id", "password_hash"}
    assert table.c.user_id.primary_key is True
    assert table.c.user_id.nullable is False
    assert table.c.password_hash.nullable is False


def test_credential_mapper_round_trip() -> None:
    credential = PasswordCredential(
        user_id=uuid4(),
        password_hash="$argon2id$opaque",
    )

    model = credential_to_model(credential)
    restored = model_to_credential(model)

    assert restored == credential
```

Add isolated repository tests using an `AsyncSession` mock to prove:
- `add()` calls `add + flush`, never commit/rollback;
- `get_by_user_id()` returns mapped credential/None;
- `replace_hash()` issues compare-and-replace and returns `True` when one row updated, `False` when zero;
- structured PK duplicate becomes `CredentialAlreadyExistsError`;
- other SQLAlchemy errors become `CredentialRepositoryError`;
- raw `IntegrityError` never leaks.

Run:

```bash
python -m pytest tests/test_credential_orm_repository.py -v
```

Expected RED because model/mapper/repository do not exist.

- [ ] **Step 2.3: Implement `UserCredentialModel`**

Create:

```python
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, PrimaryKeyConstraint, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class UserCredentialModel(Base):
    __tablename__ = "user_credentials"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", name="pk_user_credentials"),
        ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_credentials_user_id_users",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
```

Do not add `ON DELETE CASCADE`, email, role, salt column, timestamps, or a `$argon2id$` database CHECK.

- [ ] **Step 2.4: Implement pure mapping**

Create `credential_mapper.py`:

```python
from app.application.security.credentials import PasswordCredential
from app.infrastructure.database.models.user_credential import UserCredentialModel


def credential_to_model(credential: PasswordCredential) -> UserCredentialModel:
    return UserCredentialModel(
        user_id=credential.user_id,
        password_hash=credential.password_hash,
    )


def model_to_credential(model: UserCredentialModel) -> PasswordCredential:
    return PasswordCredential(
        user_id=model.user_id,
        password_hash=model.password_hash,
    )
```

- [ ] **Step 2.5: Implement the thin SQLAlchemy credential repository**

Create `sqlalchemy_credential_repository.py` using:
- injected `AsyncSession`;
- `session.add()` + `flush()` for `add`;
- `session.get(UserCredentialModel, user_id)` for lookup;
- SQLAlchemy `update(UserCredentialModel).where(user_id == ..., password_hash == expected_hash).values(password_hash=replacement_hash)` for compare-and-replace;
- `result.rowcount == 1` for success;
- structured SQLSTATE `23505` + constraint `pk_user_credentials` for `CredentialAlreadyExistsError`;
- `CredentialRepositoryError` for other SQLAlchemy failures.

Never parse `"duplicate key"` or a constraint name from `str(exc)`.

Do not call commit/rollback/close.

- [ ] **Step 2.6: Add the credential migration**

Create revision:

```python
revision = "20260829a001"
down_revision = "20260824a001"
```

`upgrade()` creates exactly:

```text
user_credentials
├── user_id UUID NOT NULL
├── password_hash TEXT NOT NULL
├── pk_user_credentials
└── fk_user_credentials_user_id_users
```

`downgrade()` drops `user_credentials`.

Update Alembic model registration so `Base.metadata` includes both `UserModel` and `UserCredentialModel`.

Autogenerate may be used only as a draft; manually review final DDL against this plan before keeping it.

- [ ] **Step 2.7: Run structural GREEN**

```bash
python -m pytest tests/test_credential_orm_repository.py -v
python -m alembic heads
python -m alembic history
```

Expected head: `20260829a001`.

- [ ] **Step 2.8: Add real PostgreSQL integration tests**

`test_credential_postgres.py` must prove on real PostgreSQL:

1. migration upgrade creates exact columns/types/PK/FK;
2. downgrade removes only the credential table and re-upgrade restores it;
3. `add()` is not durable until external commit;
4. committed credential is visible in a fresh session;
5. duplicate credential PK becomes `CredentialAlreadyExistsError`;
6. raw `IntegrityError` does not cross the adapter;
7. external rollback removes an uncommitted credential;
8. `replace_hash(user_id, expected, replacement)` returns `True` and persists only after external commit;
9. stale expected hash returns `False` and does not overwrite;
10. repository never commits or rolls back.

Fixtures may create `User` rows directly through the approved `UserRepository`; that is test setup, not provisioning.

- [ ] **Step 2.9: Run PostgreSQL Gate B**

```bash
python -m pytest tests/integration/test_credential_postgres.py -v -m postgres_integration
python -m pytest tests/integration -v -m postgres_integration
python -m pytest -q
python -m ruff check \
  app/infrastructure/database/models/user_credential.py \
  app/infrastructure/database/mappers/credential_mapper.py \
  app/infrastructure/repositories/sqlalchemy_credential_repository.py \
  tests/test_credential_orm_repository.py \
  tests/integration/test_credential_postgres.py
python -m mypy \
  app/application/security/credentials.py \
  app/infrastructure/repositories/sqlalchemy_credential_repository.py
git diff --check
```

Required: 0 failures.

- [ ] **Step 2.10: STOP for Gate `03-B`**

Do not start JWT/login work.

- [ ] **Step 2.11: After Gate approval, controlled commit/push**

Suggested commit:

```bash
git commit -m "feat: add password credential persistence"
```

Verify/push/freeze new baseline, cleanup project Docker resources, then STOP.

---

### Task 3: NF-AUTH-03-C — JWT Service + Authentication Core

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/domain/entities/user.py`
- Create: `backend/app/application/security/clock.py`
- Create: `backend/app/application/security/tokens.py`
- Create: `backend/app/application/security/authentication.py`
- Create: `backend/app/infrastructure/security/system_clock.py`
- Create: `backend/app/infrastructure/security/jwt_access_token_service.py`
- Create: `backend/tests/test_authentication_core.py`
- Create: `backend/tests/test_jwt_access_token.py`

**Interfaces:**
- Produces:
  - `canonicalize_user_email(raw_email: str) -> str`.
  - `Clock.now() -> datetime`.
  - `AccessTokenService.issue/validate`.
  - `IssuedAccessToken`, `AccessPrincipal`, `InvalidAccessTokenError`.
  - `AuthenticateCommand`, `AuthenticationResult`, `PasswordRehashCandidate`, `AuthenticationError`, `AuthenticateUser`.
- Consumes: approved `UserRepository`, credential repository, `PasswordHasher`.

- [ ] **Step 3.1: Add PyJWT crypto dependency only**

Add:

```toml
"PyJWT[crypto]>=2.13.0,<3.0.0",
```

Run:

```bash
python -m pip install -e ".[dev]"
python -m pip check
```

- [ ] **Step 3.2: Expose the existing canonical email rule without changing semantics**

First extend `tests/test_user_domain.py`:

```python
from app.domain.entities.user import canonicalize_user_email


def test_public_email_canonicalization_matches_user_create() -> None:
    raw = "  Richard.Milian+lab@Example.COM  "
    assert canonicalize_user_email(raw) == User.create(
        raw, UserRole.ANALYST
    ).email
```

Run test and observe RED.

In `user.py`, rename/expose the current helper as:

```python
def canonicalize_user_email(raw_email: str) -> str:
    if not isinstance(raw_email, str):
        raise InvalidUserEmailError("email must be a string")

    canonical = raw_email.strip().lower()
    _validate_email(canonical)
    return canonical
```

Update `User.create()` to call that public function. Do not change any validation rule.

Run all `test_user_domain.py` tests; expected GREEN with no semantic change.

- [ ] **Step 3.3: Define Clock and access-token contracts**

Create `clock.py`:

```python
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        ...
```

Create `tokens.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.entities.user import User, UserRole


class InvalidAccessTokenError(RuntimeError):
    pass


@dataclass(frozen=True)
class IssuedAccessToken:
    raw_token: str
    expires_at: datetime
    jti: UUID


@dataclass(frozen=True)
class AccessPrincipal:
    user_id: UUID
    role: UserRole
    issued_at: datetime
    expires_at: datetime
    jti: UUID


class AccessTokenService(Protocol):
    def issue(self, user: User) -> IssuedAccessToken:
        ...

    def validate(self, raw_token: str) -> AccessPrincipal:
        ...
```

Create `system_clock.py`:

```python
from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
```

- [ ] **Step 3.4: Write JWT negative matrix before adapter**

`test_jwt_access_token.py` must contain fixtures generating an RSA test keypair with `cryptography` only inside tests and a frozen UTC clock.

Required tests:
- valid PS256 token accepted;
- header `typ` exactly `neurofin-access+jwt`;
- required claim set exactly present;
- issuer exact;
- audience exact;
- subject UUID;
- `jti` UUID;
- role exact;
- nominal `exp - iat == 600`;
- second issuance gets different `jti`;
- tampered signature rejected;
- expired beyond leeway rejected;
- wrong issuer rejected;
- wrong audience rejected;
- invalid subject rejected;
- invalid `jti` rejected;
- unknown role rejected;
- each missing mandatory claim rejected;
- HS256/RS256/`none` or other forbidden algorithm rejected;
- wrong `typ` rejected;
- malformed JWT rejected;
- no email/password/password_hash/refresh fields in payload.

Run and observe RED.

- [ ] **Step 3.5: Implement PS256 adapter**

Create `jwt_access_token_service.py` with constants:

```python
_ALGORITHM = "PS256"
_TYPE = "neurofin-access+jwt"
_ISSUER = "urn:neurofin:auth"
_AUDIENCE = "urn:neurofin:api"
_ACCESS_TTL_SECONDS = 600
_LEEWAY_SECONDS = 30
_REQUIRED_CLAIMS = ("sub", "iss", "aud", "iat", "exp", "jti", "role")
```

Constructor:

```python
def __init__(
    self,
    private_key_pem: str,
    public_key_pem: str,
    clock: Clock,
) -> None:
    ...
```

Issuance:
- sample `now = clock.now()` and require timezone-aware UTC;
- `jti = uuid4()`;
- encode only seven mandatory claims;
- fixed algorithm/header;
- return raw token, exact nominal expiration, jti.

Validation:
- syntactically obtain header only to check expected `typ`; never use header `alg` to select validation algorithm;
- call PyJWT decode with `algorithms=["PS256"]`, exact issuer/audience, `require` list, fixed leeway;
- convert `sub` and `jti` through `UUID(...)`;
- convert role through `UserRole(...)`;
- construct no principal on failure;
- translate any PyJWT/claim/type/value failure to `InvalidAccessTokenError` with sanitized message;
- never log the JWT.

Run the JWT matrix; expected GREEN.

- [ ] **Step 3.6: Define non-enumerating authentication result types**

Create in `authentication.py`:

```python
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.user import User


class AuthenticationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthenticateCommand:
    email: str
    password: str


@dataclass(frozen=True)
class PasswordRehashCandidate:
    user_id: UUID
    expected_hash: str
    replacement_hash: str


@dataclass(frozen=True)
class AuthenticationResult:
    user: User
    rehash: PasswordRehashCandidate | None
```

`AuthenticationResult` never contains plaintext password.

- [ ] **Step 3.7: Write login-core tests before implementation**

`test_authentication_core.py` uses in-memory fakes implementing existing ports and a spy password hasher.

Required behavior:
- valid email/password returns current `User`;
- raw email is canonicalized by `canonicalize_user_email`;
- repository receives canonical email;
- unknown email raises `AuthenticationError` and spy proves dummy verification was invoked;
- syntactically invalid email also produces generic authentication failure and dummy verification;
- wrong password raises same `AuthenticationError`;
- known user with missing credential raises same external error and executes controlled dummy verification;
- malformed stored PHC becomes same external `AuthenticationError`;
- `needs_rehash=False` returns no rehash candidate;
- `needs_rehash=True` returns candidate with `expected_hash` + a newly produced replacement PHC;
- plaintext is absent from result and exception strings.

Run and observe RED.

- [ ] **Step 3.8: Implement `AuthenticateUser`**

Constructor receives:

```python
UserRepository
CredentialRepository
PasswordHasher
dummy_password_hash: str
```

Execution order:

```text
canonicalize email
    ↓
lookup User
    ↓
unknown/invalid input -> dummy verify -> generic AuthenticationError
    ↓
lookup PasswordCredential
    ↓
missing -> dummy verify -> generic AuthenticationError
    ↓
verify real PHC
    ↓
false/malformed -> generic AuthenticationError
    ↓
needs_rehash?
    ├── no -> result(User, None)
    └── yes -> hash current plaintext once -> result(User, candidate)
```

Use helper `_perform_dummy_verification(password)` that ignores only mismatch but converts malformed configured dummy PHC to a controlled internal error; do not expose account existence.

Do not return access/refresh tokens yet.

- [ ] **Step 3.9: Run Gate C verification**

```bash
python -m pytest tests/test_user_domain.py tests/test_authentication_core.py tests/test_jwt_access_token.py -v
python -m pytest -q
python -m ruff check \
  app/application/security \
  app/infrastructure/security \
  app/domain/entities/user.py \
  tests/test_authentication_core.py \
  tests/test_jwt_access_token.py
python -m mypy \
  app/application/security \
  app/infrastructure/security/jwt_access_token_service.py \
  app/infrastructure/security/system_clock.py
python -m pip check
git diff --check
```

Required: JWT/login matrix PASS, regression 0 failures.

- [ ] **Step 3.10: STOP for Gate `03-C`**

No refresh schema or session issuance yet.

- [ ] **Step 3.11: After Gate approval, controlled commit/push**

Suggested commit:

```bash
git commit -m "feat: add JWT authentication core"
```

Freeze baseline and STOP.

---

### Task 4: NF-AUTH-03-D — Refresh Persistence Model + Token Cryptography

**Files:**
- Create: `backend/app/application/security/refresh.py`
- Create: `backend/app/infrastructure/security/refresh_token_service.py`
- Create: `backend/app/infrastructure/database/models/refresh.py`
- Modify: `backend/app/infrastructure/database/models/__init__.py`
- Create: `backend/app/infrastructure/database/mappers/refresh_mapper.py`
- Create: `backend/app/infrastructure/repositories/sqlalchemy_refresh_repository.py`
- Modify: `backend/alembic/env.py`
- Modify: `backend/tests/test_alembic_foundation.py`
- Create: `backend/alembic/versions/20260829a002_create_refresh_sessions.py`
- Create: `backend/tests/test_refresh_crypto.py`
- Create: `backend/tests/test_refresh_orm_repository.py`
- Create: `backend/tests/integration/test_refresh_schema_postgres.py`

**Interfaces:**
- Produces refresh records, `RefreshRepository`, `RefreshTokenService`, strict CSPRNG token adapter, exact schema, lookup and lock primitives.
- Does not yet implement rotation or logout service behavior.

- [ ] **Step 4.1: Docker/PostgreSQL preflight**

Same strict preflight as `03-B`. Docker not ready -> STOP before edits.

- [ ] **Step 4.2: Define pure refresh Application records and ports**

Create `refresh.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


class RefreshAuthenticationError(RuntimeError):
    pass


class InvalidRefreshTokenError(ValueError):
    pass


@dataclass(frozen=True)
class IssuedRefreshToken:
    raw_token: str
    token_hash: bytes


@dataclass(frozen=True)
class RefreshSessionRecord:
    id: UUID
    user_id: UUID
    created_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class RefreshTokenRecord:
    id: UUID
    session_id: UUID
    parent_token_id: UUID | None
    token_hash: bytes
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None


class RefreshTokenService(Protocol):
    def issue(self) -> IssuedRefreshToken:
        ...

    def digest(self, raw_token: str) -> bytes:
        ...


class RefreshRepository(Protocol):
    async def add_session(self, record: RefreshSessionRecord) -> None:
        ...

    async def add_token(self, record: RefreshTokenRecord) -> None:
        ...

    async def find_token_by_hash(self, token_hash: bytes) -> RefreshTokenRecord | None:
        ...

    async def lock_session(self, session_id: UUID) -> RefreshSessionRecord | None:
        ...

    async def lock_token(self, token_id: UUID) -> RefreshTokenRecord | None:
        ...

    async def mark_token_consumed(self, token_id: UUID, consumed_at: datetime) -> None:
        ...

    async def revoke_session(self, session_id: UUID, revoked_at: datetime) -> None:
        ...
```

No SQLAlchemy types enter this file.

- [ ] **Step 4.3: Write strict refresh crypto tests first**

Required tests:
- each issue returns exactly 43 characters;
- regex `^[A-Za-z0-9_-]{43}$`;
- no `=`, `+`, `/`, whitespace;
- strict decode length = 32;
- two issued tokens differ;
- token hash length = 32 bytes;
- `digest(raw)` equals issued digest;
- malformed length rejected;
- forbidden alphabet rejected;
- non-canonical padded input rejected;
- 32-byte decoded canonical representation round-trips uniquely.

Run RED.

- [ ] **Step 4.4: Implement CSPRNG/Base64URL/SHA-256 adapter**

Create `refresh_token_service.py`:

```python
import base64
import hashlib
import re
import secrets

from app.application.security.refresh import (
    InvalidRefreshTokenError,
    IssuedRefreshToken,
)

_CANONICAL = re.compile(r"^[A-Za-z0-9_-]{43}$")


class SecureRefreshTokenService:
    def issue(self) -> IssuedRefreshToken:
        secret = secrets.token_bytes(32)
        raw = base64.urlsafe_b64encode(secret).decode("ascii").rstrip("=")
        return IssuedRefreshToken(
            raw_token=raw,
            token_hash=hashlib.sha256(secret).digest(),
        )

    def digest(self, raw_token: str) -> bytes:
        if not isinstance(raw_token, str) or _CANONICAL.fullmatch(raw_token) is None:
            raise InvalidRefreshTokenError("invalid refresh token")

        try:
            decoded = base64.urlsafe_b64decode(raw_token + "=")
        except Exception as exc:
            raise InvalidRefreshTokenError("invalid refresh token") from exc

        if len(decoded) != 32:
            raise InvalidRefreshTokenError("invalid refresh token")

        canonical = base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
        if canonical != raw_token:
            raise InvalidRefreshTokenError("invalid refresh token")

        return hashlib.sha256(decoded).digest()
```

Use a narrower base64 exception if the runtime exposes one cleanly; never echo raw input in errors.

Run crypto tests; expected GREEN.

- [ ] **Step 4.5: Write ORM structural tests first**

Expected tables:

```text
refresh_sessions
├── id UUID PK NOT NULL
├── user_id UUID FK users.id NOT NULL
├── created_at TIMESTAMPTZ NOT NULL
├── absolute_expires_at TIMESTAMPTZ NOT NULL
└── revoked_at TIMESTAMPTZ NULL

refresh_tokens
├── id UUID PK NOT NULL
├── session_id UUID FK refresh_sessions.id NOT NULL
├── parent_token_id UUID FK refresh_tokens.id NULL
├── token_hash BYTEA NOT NULL
├── issued_at TIMESTAMPTZ NOT NULL
├── expires_at TIMESTAMPTZ NOT NULL
└── consumed_at TIMESTAMPTZ NULL
```

Named constraints:
- `pk_refresh_sessions`
- `fk_refresh_sessions_user_id_users`
- `ck_refresh_sessions_absolute_expiry`
- `pk_refresh_tokens`
- `fk_refresh_tokens_session_id_refresh_sessions`
- `fk_refresh_tokens_parent_token_id_refresh_tokens`
- `uq_refresh_tokens_token_hash`
- `uq_refresh_tokens_parent_token_id`
- `ck_refresh_tokens_hash_length`
- `ck_refresh_tokens_expiry`

No delete cascade.

Run RED.

- [ ] **Step 4.6: Implement refresh ORM models and pure mapping**

Use `DateTime(timezone=True)`, PostgreSQL UUID, and `LargeBinary`.

`token_hash` physical length is defended by:

```sql
octet_length(token_hash) = 32
```

Time defenses:
- session `absolute_expires_at > created_at`;
- token `expires_at > issued_at`.

Mappers copy values only. They do not calculate expiry, generate UUIDs, canonicalize tokens, or execute SQL.

- [ ] **Step 4.7: Implement thin `SQLAlchemyRefreshRepository`**

Required behavior:
- `add_session/add_token`: add + flush;
- `find_token_by_hash`: normal `SELECT`, no lock;
- `lock_session`: `SELECT ... WHERE id = ? FOR UPDATE`;
- `lock_token`: `SELECT ... WHERE id = ? FOR UPDATE`;
- `mark_token_consumed`: update exact row + flush;
- `revoke_session`: set `revoked_at` only when needed + flush;
- no commit/rollback/close;
- repository errors sanitized and causally chained.

The repository does not decide whether a token is expired/reused; it exposes locked state to the state machine.

- [ ] **Step 4.8: Add Alembic refresh migration**

Create:

```python
revision = "20260829a002"
down_revision = "20260829a001"
```

Create `refresh_sessions` first, then `refresh_tokens`.

Downgrade drops `refresh_tokens` first, then `refresh_sessions`.

Register models in `alembic/env.py`.

- [ ] **Step 4.9: Add real PostgreSQL schema/repository primitive tests**

Prove:
- upgrade/down/re-upgrade;
- exact columns and constraint names;
- `BYTEA` digest length defense;
- unique digest;
- unique parent token ID;
- FK session/user defenses;
- timezone-aware timestamp types;
- lock methods compile/execute on PostgreSQL;
- `add_*` visibility depends on external commit;
- external rollback works.

Do not test the full rotation state machine yet.

- [ ] **Step 4.10: Run Gate D**

```bash
python -m pytest tests/test_refresh_crypto.py tests/test_refresh_orm_repository.py -v
python -m pytest tests/integration/test_refresh_schema_postgres.py -v -m postgres_integration
python -m pytest tests/integration -v -m postgres_integration
python -m pytest -q
python -m ruff check \
  app/application/security/refresh.py \
  app/infrastructure/security/refresh_token_service.py \
  app/infrastructure/database/models/refresh.py \
  app/infrastructure/database/mappers/refresh_mapper.py \
  app/infrastructure/repositories/sqlalchemy_refresh_repository.py \
  tests/test_refresh_crypto.py \
  tests/test_refresh_orm_repository.py \
  tests/integration/test_refresh_schema_postgres.py
python -m mypy \
  app/application/security/refresh.py \
  app/infrastructure/security/refresh_token_service.py \
  app/infrastructure/repositories/sqlalchemy_refresh_repository.py
git diff --check
```

Required: 0 failures.

- [ ] **Step 4.11: STOP for Gate `03-D`**

- [ ] **Step 4.12: After Gate approval, controlled commit/push**

Suggested commit:

```bash
git commit -m "feat: add refresh session persistence"
```

Cleanup Docker and STOP.

---

### Task 5: NF-AUTH-03-E — Session Issuance on Successful Login

**Files:**
- Create: `backend/app/application/security/sessions.py`
- Create: `backend/app/infrastructure/security/sqlalchemy_login_session_service.py`
- Create: `backend/tests/test_login_session_service.py`
- Create: `backend/tests/integration/test_login_session_postgres.py`

**Interfaces:**
- Produces `AuthSessionTokens`, `LoginSessionService`, concrete `SQLAlchemyLoginSessionService`.
- Uses separate SQLAlchemy session scopes for authentication read, core durable session creation, and optional rehash maintenance.
- No public HTTP endpoint yet.

- [ ] **Step 5.1: Docker/PostgreSQL preflight**

Real PostgreSQL is mandatory for this Gate because core session issuance must be proven atomic.

- [ ] **Step 5.2: Define session service contracts**

Create `sessions.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class AuthSessionTokens:
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


class LoginSessionService(Protocol):
    async def login(self, email: str, password: str) -> AuthSessionTokens:
        ...


class RefreshSessionService(Protocol):
    async def refresh(self, raw_refresh_token: str) -> AuthSessionTokens:
        ...


class LogoutService(Protocol):
    async def logout(self, raw_refresh_token: str | None) -> None:
        ...
```

These are use-case contracts; concrete transaction-aware implementations remain Infrastructure.

- [ ] **Step 5.3: Write login-service tests before implementation**

Use fakes for isolated tests and real PostgreSQL for integration.

Required isolated behavior:
- delegates credential validation to `AuthenticateUser`;
- access token and R1 are prepared but not exposed before durable core transaction;
- session ID/token ID are application-generated UUIDs;
- absolute expiry = `now + 8h`;
- R1 expiry = `min(now + 30m, absolute_expiry)`;
- R1 parent is `None`;
- post-commit rehash compare-and-replace uses exact candidate;
- rehash `False` result is non-error;
- rehash repository failure after core commit does not fail login.

Run RED.

- [ ] **Step 5.4: Implement `SQLAlchemyLoginSessionService`**

Constructor receives:
- `async_sessionmaker[AsyncSession]`;
- `PasswordHasher`;
- `AccessTokenService`;
- `RefreshTokenService`;
- `Clock`;
- `dummy_password_hash`.

Execution:

```text
SESSION A
  UserRepository + CredentialRepository
  AuthenticateUser.execute(email,password)
  end read transaction/session
        ↓
sample authoritative now
create RefreshSessionRecord
issue raw R1/digest
issue access JWT
        ↓
SESSION B
  BEGIN
  RefreshRepository.add_session(S1)
  RefreshRepository.add_token(R1 digest)
  COMMIT
        ↓
core login durable
        ↓
if rehash candidate:
  SESSION C
  BEGIN
  CredentialRepository.replace_hash(expected,replacement)
  COMMIT
  failure -> rollback maintenance only
        ↓
return access JWT + raw R1
```

No raw token is persisted.

If SESSION B fails:
- transaction rolls back;
- service raises a sanitized session-creation error;
- neither access nor refresh artifact is returned.

Do not revoke a successfully committed session if the later rehash maintenance fails.

- [ ] **Step 5.5: Add real PostgreSQL tests**

Prepare user + credential only through controlled test setup.

Prove:
1. successful login creates exactly one active refresh family and R1 digest;
2. raw R1 is absent from DB;
3. committed S1/R1 visible from fresh session;
4. `absolute_expires_at = created_at + 8h`;
5. R1 expires no later than 30m and no later than absolute expiry;
6. forced R1 insert failure rolls back S1 and returns no result;
7. login with stale hash commits S1/R1 first, then compare-and-replace;
8. forced rehash failure leaves S1 active and login result successful;
9. no provisioning endpoint is introduced.

Use a frozen `Clock` for deterministic timestamp assertions.

- [ ] **Step 5.6: Run Gate E**

```bash
python -m pytest tests/test_login_session_service.py -v
python -m pytest tests/integration/test_login_session_postgres.py -v -m postgres_integration
python -m pytest -q
python -m ruff check \
  app/application/security/sessions.py \
  app/infrastructure/security/sqlalchemy_login_session_service.py \
  tests/test_login_session_service.py \
  tests/integration/test_login_session_postgres.py
python -m mypy \
  app/application/security/sessions.py \
  app/infrastructure/security/sqlalchemy_login_session_service.py
git diff --check
```

- [ ] **Step 5.7: STOP for Gate `03-E`**

- [ ] **Step 5.8: After Gate approval, controlled commit/push**

Suggested commit:

```bash
git commit -m "feat: issue durable authentication sessions"
```

STOP.

---

### Task 6: NF-AUTH-03-F — Atomic Refresh Rotation + Replay/Reuse

**Files:**
- Create: `backend/app/infrastructure/security/sqlalchemy_refresh_session_service.py`
- Create: `backend/tests/test_refresh_session_service.py`
- Create: `backend/tests/integration/test_refresh_rotation_postgres.py`

**Interfaces:**
- Implements `RefreshSessionService`.
- Uses `RefreshRepository`, `UserRepository`, `AccessTokenService`, `RefreshTokenService`, `Clock`.
- PostgreSQL transaction + lock semantics are authoritative.

- [ ] **Step 6.1: Docker/PostgreSQL preflight**

If real PostgreSQL is not healthy, STOP before edits.

- [ ] **Step 6.2: Write state-machine tests first**

Isolated tests must cover:
- malformed raw refresh -> generic `RefreshAuthenticationError`, no DB mutation;
- unknown digest -> generic failure, no mutation;
- revoked family -> failure, no mutation;
- absolute-expired family -> failure;
- unconsumed token expired -> failure;
- consumed token in active family -> reuse branch, family revocation;
- valid token -> consume + successor + new access token.

The decision order asserted by tests is:

```text
session revoked
absolute session expired
token consumed -> reuse/revoke
token expired
valid rotate
```

Run RED.

- [ ] **Step 6.3: Implement pre-read + authoritative locked transaction**

Algorithm:

```text
strict digest(raw)
    ↓
SESSION A read-only:
find token by digest
    ↓
unknown -> generic failure
    ↓
capture token.id + session_id
close A
    ↓
SESSION B:
BEGIN
lock session FOR UPDATE
lock token FOR UPDATE
re-sample now
revalidate
```

Use only lock order `session -> token`.

Do not use `SKIP LOCKED` or `NOWAIT`.

- [ ] **Step 6.4: Implement valid rotation**

Inside the locked transaction:
1. load authoritative current `User` by `session.user_id`;
2. issue new raw R2 + digest;
3. issue new access JWT while transaction can still roll back if signing fails;
4. mark R1 consumed at current `now`;
5. create R2 with `parent_token_id = R1.id`;
6. `R2.expires_at = min(now + 30m, session.absolute_expires_at)`;
7. flush;
8. normal transaction exit commits.

Only after commit return raw R2 + access JWT.

- [ ] **Step 6.5: Implement reuse with commit-before-reject**

For consumed token + active family:

```text
inside transaction:
  revoke_session(now)
  mark outcome = REUSE
exit transaction normally -> COMMIT
after commit:
  raise RefreshAuthenticationError("refresh authentication failed")
```

Do not raise the outward exception inside a context that would roll back the revocation.

- [ ] **Step 6.6: Add real same-R1 concurrency test**

Use two independent sessions/tasks and an `asyncio.Event`/barrier so both requests present the same R1 concurrently.

Required postconditions:

```text
at most one successful successor
R1.consumed_at != NULL
children(R1) <= 1
second use detects reuse
refresh_session.revoked_at != NULL
successful R2, if returned, cannot refresh again because family is revoked
```

A sequential double-call is not sufficient evidence.

- [ ] **Step 6.7: Add real rollback-on-successor-insert-failure test**

Force a real PostgreSQL uniqueness failure by using a test refresh-token service whose proposed R2 digest collides with an existing unique `token_hash`.

Required after service failure:

```text
R1.consumed_at IS NULL
no successor row committed
family remains in the pre-failure state unless another rule required revocation
```

This proves atomic rollback rather than mocked rollback.

- [ ] **Step 6.8: Verify consumed-after-expiry still classifies as reuse**

Prepare:
- active family;
- R1 consumed;
- advance frozen clock beyond R1 token expiry but before absolute session expiry.

Present R1.

Required:
- reuse branch wins over token-expired branch;
- family is revoked.

- [ ] **Step 6.9: Run Gate F**

```bash
python -m pytest tests/test_refresh_session_service.py -v
python -m pytest tests/integration/test_refresh_rotation_postgres.py -v -m postgres_integration
python -m pytest -q
python -m ruff check \
  app/infrastructure/security/sqlalchemy_refresh_session_service.py \
  tests/test_refresh_session_service.py \
  tests/integration/test_refresh_rotation_postgres.py
python -m mypy app/infrastructure/security/sqlalchemy_refresh_session_service.py
git diff --check
```

Required: all concurrency and rollback scenarios PASS.

- [ ] **Step 6.10: STOP for Gate `03-F`**

- [ ] **Step 6.11: After Gate approval, controlled commit/push**

Suggested commit:

```bash
git commit -m "feat: add atomic refresh rotation"
```

Cleanup and STOP.

---

### Task 7: NF-AUTH-03-G — Logout + Family Revocation

**Files:**
- Create: `backend/app/infrastructure/security/sqlalchemy_logout_service.py`
- Create: `backend/tests/test_logout_service.py`
- Create: `backend/tests/integration/test_logout_postgres.py`

**Interfaces:**
- Implements `LogoutService`.
- Reuses the same `session -> token` lock order as refresh.
- Outward behavior is idempotent; internal known-consumed state still triggers reuse-family revocation.

- [ ] **Step 7.1: Docker/PostgreSQL preflight**

Real PostgreSQL is required for the race Gate.

- [ ] **Step 7.2: Write logout tests first**

Required cases:
- `None` refresh -> success, no mutation;
- malformed raw -> success, no mutation;
- unknown digest -> success, no mutation;
- active known family -> revoke + success;
- already revoked -> success without required extra mutation;
- known expired token in active family -> revoke + success;
- known consumed token in active family -> family revoke + success outward;
- other user sessions remain active.

Run RED.

- [ ] **Step 7.3: Implement logout service**

Algorithm:
1. missing/malformed/unknown: return normally;
2. pre-read known token to obtain IDs;
3. open transaction;
4. lock session then token;
5. revalidate current rows;
6. if family active, set `revoked_at=now`;
7. commit;
8. return normally.

For known consumed tokens, the internal reason is reuse, but HTTP-facing logout remains idempotent success.

Do not delete session/token rows.

- [ ] **Step 7.4: Add real refresh-vs-logout race**

Start from active R1.

Run refresh and logout concurrently with independent transactions.

Required final invariant regardless of lock winner:

```text
refresh_session.revoked_at != NULL
usable successor = 0
```

If refresh commits R2 first, logout revokes the family and R2 must subsequently fail.

If logout commits first, refresh must observe revoked family and fail without successor.

- [ ] **Step 7.5: Prove access JWT is not denylisted**

Issue an access JWT, perform logout, then validate the pre-logout access JWT with a clock still inside its allowed temporal window.

Required:
- refresh family revoked;
- access JWT remains valid until time-based validation fails.

Advance frozen clock beyond expiration + permitted leeway and verify rejection.

- [ ] **Step 7.6: Run Gate G**

```bash
python -m pytest tests/test_logout_service.py -v
python -m pytest tests/integration/test_logout_postgres.py -v -m postgres_integration
python -m pytest -q
python -m ruff check \
  app/infrastructure/security/sqlalchemy_logout_service.py \
  tests/test_logout_service.py \
  tests/integration/test_logout_postgres.py
python -m mypy app/infrastructure/security/sqlalchemy_logout_service.py
git diff --check
```

- [ ] **Step 7.7: STOP for Gate `03-G`**

- [ ] **Step 7.8: After Gate approval, controlled commit/push**

Suggested commit:

```bash
git commit -m "feat: add refresh family logout"
```

STOP.

---

### Task 8: NF-AUTH-03-H — Browser Transport + Auth HTTP Surface

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/infrastructure/security/key_loader.py`
- Create: `backend/app/presentation/security.py`
- Create: `backend/app/presentation/api/v1/schemas/auth.py`
- Create: `backend/app/presentation/api/v1/endpoints/auth.py`
- Modify: `backend/app/presentation/api/v1/router.py`
- Modify: `backend/app/presentation/dependencies.py`
- Modify: `backend/app/main.py`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `backend/tests/test_auth_http.py`

**Interfaces:**
- Default routes under current configuration: `POST /api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/logout`.
- Access response JSON contains access token only.
- Refresh secret appears only in `Set-Cookie`.
- Browser auth endpoints require exact Origin + custom CSRF header.

- [ ] **Step 8.1: Write HTTP transport tests first**

Use `TestClient`/httpx with HTTPS base URL and dependency/runtime test fixtures.

Required tests:
- login with trusted Origin + `X-NeuroFin-CSRF: 1` calls service;
- wrong Origin rejected before service mutation;
- lookalike Origin rejected;
- `Origin: null` rejected;
- missing Origin rejected;
- missing/wrong CSRF header rejected;
- login success body includes only `access_token`, `token_type`, `expires_in`;
- login response refresh cookie exact;
- raw refresh absent from JSON;
- refresh reads cookie, rotates, sends replacement cookie;
- logout returns 204 and clears cookie;
- unknown/missing logout still clears cookie after valid transport checks;
- no valid access JWT is required for refresh/logout.

Run RED.

- [ ] **Step 8.2: Add auth settings without tracked production secrets**

Add:

```python
from pathlib import Path

auth_trusted_origin: str = "http://localhost:3000"
jwt_private_key_path: Path | None = None
jwt_public_key_path: Path | None = None
```

Do not add a private key value to source control.

Production must override `auth_trusted_origin` with the exact deployment origin and provide key files out-of-band.

- [ ] **Step 8.3: Implement key loader**

Create `key_loader.py`:

```python
from pathlib import Path


class JWTKeyConfigurationError(RuntimeError):
    pass


def load_pem(path: Path | None, label: str) -> str:
    if path is None:
        raise JWTKeyConfigurationError(f"{label} path is not configured")

    try:
        data = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise JWTKeyConfigurationError(f"{label} could not be loaded") from exc

    if "BEGIN" not in data or "KEY" not in data:
        raise JWTKeyConfigurationError(f"{label} is not valid PEM text")

    return data
```

Do not include path contents or key contents in logs/errors.

- [ ] **Step 8.4: Define Presentation schemas**

Create `schemas/auth.py`:

```python
from typing import Literal

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = 600
```

Do not use `EmailStr` here: Domain authentication must own email semantics, and malformed/unknown identifiers must converge on the same auth failure behavior rather than a distinguishable 422 email-format branch.

- [ ] **Step 8.5: Implement exact Origin/CSRF checks and cookie helpers**

Create `presentation/security.py` with constants:

```python
REFRESH_COOKIE_NAME = "__Host-neurofin_refresh"
CSRF_HEADER_NAME = "X-NeuroFin-CSRF"
CSRF_HEADER_VALUE = "1"
```

`enforce_browser_auth_request(request, settings)`:
- read `Origin`;
- require exact equality to `settings.auth_trusted_origin`;
- require `X-NeuroFin-CSRF == "1"`;
- reject with 403 before service invocation.

Cookie writer:

```python
response.set_cookie(
    key=REFRESH_COOKIE_NAME,
    value=raw_refresh,
    max_age=max_age_seconds,
    httponly=True,
    secure=True,
    samesite="strict",
    path="/",
)
```

Do not pass `domain`.

Cookie clearer must use `Max-Age=0` semantics and compatible path/security attributes.

- [ ] **Step 8.6: Compose auth runtime without import-time DB side effects**

Update `main.py` lifespan to:
- obtain settings;
- create database engine/session factory only when configured;
- load configured PEM keys without logging contents;
- construct `SystemClock`, `Argon2idPasswordHasher`, JWT service, refresh-token service;
- construct login/refresh/logout services sharing the session factory;
- place them in `app.state`;
- dispose engine on shutdown.

Do not create global `AsyncSession` objects.

If auth runtime prerequisites are absent, fail explicitly when auth runtime is required; do not silently fall back to insecure auth.

- [ ] **Step 8.7: Add dependency accessors**

In `presentation/dependencies.py`, add typed accessors that retrieve the prebuilt `LoginSessionService`, `RefreshSessionService`, and `LogoutService` from `request.app.state`.

Do not disturb `get_generate_forecast_use_case()` behavior.

- [ ] **Step 8.8: Implement auth endpoints**

`auth.py` router prefix:

```python
router = APIRouter(prefix="/auth")
```

Login:
- enforce browser auth transport;
- call `login(email,password)`;
- translate `AuthenticationError`/session auth failure to generic 401;
- set refresh cookie only after service returns durable result;
- return `AccessTokenResponse`.

Refresh:
- enforce Origin/CSRF;
- read `__Host-neurofin_refresh`;
- call refresh service;
- generic 401 on invalid/expired/revoked/reused refresh;
- set rotated refresh cookie;
- return new access response.

Logout:
- enforce Origin/CSRF;
- pass cookie value or `None` to logout service;
- clear cookie;
- return 204.

Never place raw refresh in body.

- [ ] **Step 8.9: Register routes under existing API prefix**

In `presentation/api/v1/router.py`:

```python
from .endpoints.auth import router as auth_router

api_router.include_router(auth_router, tags=["Auth"])
```

Because `main.py` already mounts `api_router` with `settings.api_prefix`, the default external paths become `/api/v1/auth/...`.

Do not add root `/auth/...` duplicates.

- [ ] **Step 8.10: Tighten CORS**

Replace final broad method/header policy with:

```python
allow_origins=settings.allowed_origins
allow_credentials=True
allow_methods=["GET", "POST", "OPTIONS"]
allow_headers=["Authorization", "Content-Type", "X-NeuroFin-CSRF"]
```

No wildcard origin/method/header remains in the final auth posture.

Existing Health GET and Forecast POST remain supported.

- [ ] **Step 8.11: Add runtime-memory frontend auth transport**

Modify `frontend/src/api/client.ts` so `apiRequest` can accept an optional Bearer token without adding persistence.

Create `frontend/src/api/auth.ts`:

```typescript
import { apiRequest } from './client';

interface AccessTokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

let accessToken: string | null = null;

const csrfHeaders = {
  'X-NeuroFin-CSRF': '1',
};

export function getRuntimeAccessToken(): string | null {
  return accessToken;
}

export async function login(email: string, password: string): Promise<void> {
  const result = await apiRequest<AccessTokenResponse>('/auth/login', {
    method: 'POST',
    credentials: 'include',
    headers: csrfHeaders,
    body: JSON.stringify({ email, password }),
  });
  accessToken = result.access_token;
}

export async function refreshSession(): Promise<void> {
  const result = await apiRequest<AccessTokenResponse>('/auth/refresh', {
    method: 'POST',
    credentials: 'include',
    headers: csrfHeaders,
  });
  accessToken = result.access_token;
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<void>('/auth/logout', {
      method: 'POST',
      credentials: 'include',
      headers: csrfHeaders,
    });
  } finally {
    accessToken = null;
  }
}
```

Do not add localStorage/sessionStorage/IndexedDB.

No login page/UI is required in this phase.

- [ ] **Step 8.12: Run HTTP/browser contract Gate**

```bash
cd backend
python -m pytest tests/test_auth_http.py -v
python -m pytest -q
python -m ruff check app/presentation app/main.py tests/test_auth_http.py
python -m mypy app/presentation app/main.py
git diff --check

cd ../frontend
npm run typecheck
npm run build
grep -R -n -E "localStorage|sessionStorage|indexedDB|IndexedDB" src/api/auth.ts src/api/client.ts
```

Required:
- HTTP matrix PASS;
- backend regression 0 failures;
- frontend typecheck/build PASS;
- persistence grep returns no token-storage implementation.

- [ ] **Step 8.13: STOP for Gate `03-H`**

- [ ] **Step 8.14: After Gate approval, controlled commit/push**

Suggested commit:

```bash
git commit -m "feat: add secure browser authentication transport"
```

STOP.

---

### Task 9: NF-AUTH-03-I — Integrated Real Security Verification

**Files:**
- Create: `backend/tests/integration/test_auth_security_postgres.py`
- Create: `backend/docs/superpowers/evidence/2026-08-29-nf-auth-03-security-evidence-index.md`
- Production source modification: forbidden unless a separate corrective microiteration is explicitly opened.

**Interfaces:**
- Consumes the published `03-A…03-H` candidate.
- Produces integrated evidence and the exact `NF-SEC-00-E` AC-to-evidence crosswalk.

- [ ] **Step 9.1: Documentary precondition**

Before writing evidence mapping, obtain the canonical approved `NF-SEC-00-E` acceptance-criteria matrix.

Search/read the actual source and copy exact IDs only.

If the canonical matrix is unavailable:

```text
DOCUMENTARY INPUT NOT AVAILABLE
→ STOP
```

Do not infer numeric AC IDs from memory or prior summaries.

- [ ] **Step 9.2: Docker/PostgreSQL preflight**

Require Docker Engine, compose and project PostgreSQL health `healthy`.

No PostgreSQL -> STOP.

- [ ] **Step 9.3: Build integrated test scenarios without changing production**

`test_auth_security_postgres.py` must integrate published behavior:

1. real credential + login + durable session;
2. login unknown/wrong/missing externally indistinguishable;
3. JWT valid/expired/tampered/wrong issuer/wrong audience/invalid sub/invalid jti/unknown role/missing claim/wrong typ/forbidden algorithm/malformed;
4. raw password absent from DB/log capture;
5. raw refresh absent from DB/log capture;
6. strict 43-character refresh format;
7. valid refresh rotates R1 -> R2;
8. same-R1 real concurrency revokes family;
9. forced R2 insert uniqueness failure rolls back R1 consumption;
10. expired token rejected;
11. revoked family rejected;
12. absolute-expired session rejected;
13. consumed token after token expiry still reuse while family active;
14. logout current family;
15. logout idempotency;
16. refresh-vs-logout real race;
17. pre-logout access JWT survives logout only until temporal validation fails;
18. every newly issued access JWT reloads current `User.role`;
19. wrong/missing/null/lookalike Origin rejected before mutation;
20. missing CSRF header rejected before mutation;
21. exact cookie attributes;
22. CORS explicit allowlist behavior.

- [ ] **Step 9.4: Execute Alembic round-trip on the final auth schema**

From a disposable real PostgreSQL database:

```bash
python -m alembic upgrade head
python -m alembic current
python -m alembic downgrade 20260824a001
python -m alembic upgrade head
python -m alembic current
```

The downgrade target deliberately preserves the already-closed `users` identity table while removing both `NF-AUTH-03` auth migrations.

Then inspect physical schema/constraints.

- [ ] **Step 9.5: Run full PostgreSQL security suite**

```bash
python -m pytest tests/integration -v -m postgres_integration
python -m pytest tests/integration/test_auth_security_postgres.py -v -m postgres_integration
python -m pytest -q
```

Required: 0 failures.

- [ ] **Step 9.6: Boundary audit**

```bash
git grep -n -E "fastapi|sqlalchemy|asyncpg|alembic|jwt|argon2" -- \
  backend/app/domain \
  backend/app/application
```

Review each match.

Required:
- Domain framework/security-library imports = 0;
- Application FastAPI/SQLAlchemy/asyncpg/Alembic/JWT/Argon2 concrete imports = 0;
- Application may contain its own protocol/type names containing terms such as token/password; those are not dependency violations.

- [ ] **Step 9.7: Secret leakage audit**

Run repository searches for dangerous persistence/logging patterns and inspect results:

```bash
git grep -n -E "localStorage|sessionStorage|IndexedDB|indexedDB" -- frontend
git grep -n -E "password.*(print|log|logger)|refresh.*(print|log|logger)" -- backend/app backend/tests
git grep -n -E "PRIVATE KEY|BEGIN RSA PRIVATE KEY|BEGIN PRIVATE KEY" -- .
```

Required:
- no browser persistent token storage;
- no logging of raw password/refresh;
- no tracked production private signing key.

A test fixture key inside a test file is not permitted either; tests must generate ephemeral key material at runtime or use temporary untracked files.

- [ ] **Step 9.8: Quality gates**

```bash
cd backend
python -m ruff check app tests
python -m mypy app
python -m pytest -q
git diff --check

cd ../frontend
npm run typecheck
npm run build
```

Existing pre-authorized baseline quality debt may be classified separately, but new NF-AUTH-03 debt is 0.

- [ ] **Step 9.9: Produce exact evidence index**

Create `2026-08-29-nf-auth-03-security-evidence-index.md`.

For each applicable exact AC read from `NF-SEC-00-E`, record:
- exact AC ID;
- implementation microiteration;
- verification command/test;
- evidence artifact name using the canonical `EV-NF-SEC-<AC-ID>-<METHOD>-<NN>` scheme;
- observed result;
- Gate.

Do not invent IDs.

- [ ] **Step 9.10: If any security-critical scenario fails, STOP as NO-GO**

`03-I` is evidence work. Do not silently fix production code inside it.

A code defect opens a separately named corrective microiteration with its own RED/GREEN/Gate.

- [ ] **Step 9.11: STOP for Gate `03-I`**

After Gate approval, commit only new tests/evidence that were approved, then controlled push and STOP before independent QA.

---

### Task 10: NF-AUTH-03-J — Independent QA / Fresh-Baseline Final Audit

**Files:**
- Repository source mutation: `0`.
- QA report is returned as execution evidence; the audited clone must finish clean.

**Interfaces:**
- Consumes the published `03-I` candidate.
- Produces final `GO`, `GO WITH NON-BLOCKING OBSERVATIONS`, or `NO-GO`.

- [ ] **Step 10.1: Use a fresh clone / fresh environment**

Record:
- candidate SHA;
- branch;
- origin;
- Python version;
- pip version;
- Node/npm versions;
- Docker/Compose versions;
- PostgreSQL image/server version.

Do not reuse uncommitted developer state as QA authority.

- [ ] **Step 10.2: Fresh backend install**

From fresh clone:

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip check
```

Required: installation and dependency check PASS.

- [ ] **Step 10.3: Fresh frontend install/build**

Use the committed lockfile:

```bash
cd frontend
npm ci
npm run typecheck
npm run build
```

Required: PASS.

- [ ] **Step 10.4: Docker/PostgreSQL QA preflight**

```bash
docker info
docker compose version
```

Start only project-specific disposable PostgreSQL.

Wait for health `healthy`.

If environment unavailable, classify environment blocker; do not call the candidate defective without evidence.

- [ ] **Step 10.5: Reconstruct migrations from scratch**

On empty QA DB:

```bash
cd backend
python -m alembic upgrade head
python -m alembic current
python -m alembic downgrade 20260824a001
python -m alembic upgrade head
python -m alembic current
```

Inspect:
- `users` preserved at downgrade target;
- `user_credentials`, `refresh_sessions`, `refresh_tokens` appear/disappear according to migration graph;
- named constraints and types match design.

- [ ] **Step 10.6: Execute focused security suites**

Run all credential, JWT, login, refresh, logout, browser and PostgreSQL auth suites.

Required: 0 failures.

- [ ] **Step 10.7: Execute full backend regression with PostgreSQL active**

```bash
python -m pytest -q
```

Required: 0 failures.

Warnings are reported exactly; do not relabel an unknown warning as PASS.

- [ ] **Step 10.8: Re-run real concurrency evidence independently**

Specifically rerun:
- same-R1 concurrent refresh;
- rollback on forced successor insert failure;
- refresh-vs-logout race.

Sequential substitutes are not accepted.

- [ ] **Step 10.9: Re-run JWT negative matrix independently**

Confirm fixed PS256 allowlist and every required negative case.

No key material is committed to Git.

- [ ] **Step 10.10: Re-run browser transport contract independently**

Confirm:
- exact cookie;
- Origin allow/reject matrix;
- CSRF header;
- CORS explicitness;
- refresh absent from JSON;
- access token not persisted in browser storage code.

- [ ] **Step 10.11: Re-run Clean Architecture and secret audits**

Required:
- Domain concrete framework/security dependency count = 0;
- Application concrete FastAPI/SQLAlchemy/JWT/Argon2/cookie dependency count = 0;
- tracked private key = 0;
- plaintext password/raw refresh persistence/logging = 0.

- [ ] **Step 10.12: Verify zero source mutation**

Before and after QA:

```bash
git status --short --untracked-files=all
git diff --check
git rev-parse HEAD
```

Required:
- audited SHA unchanged;
- source mutation = 0;
- working tree clean after test-generated temporary artifacts are removed only through documented test cleanup, not `git clean`.

- [ ] **Step 10.13: Cleanup Docker resources**

Stop/remove only the NeuroFin QA resources created by this run.

Do not touch unrelated containers/networks/volumes.

Verify no project QA resources remain unexpectedly.

- [ ] **Step 10.14: Issue the final QA report**

Report exact evidence, including:
- SHA;
- ordinary/full/PostgreSQL counts;
- migration round-trip;
- concurrency results;
- JWT matrix;
- browser security matrix;
- boundary audit;
- secret audit;
- source mutation;
- Docker cleanup.

Allowed final outcomes:

```text
GO
GO WITH NON-BLOCKING OBSERVATIONS
NO-GO
```

Any security-critical failure -> `NO-GO`.

- [ ] **Step 10.15: Final STOP**

Only after independent QA `GO` or architecturally accepted `GO WITH NON-BLOCKING OBSERVATIONS` may the architecture lead declare:

```text
NF-AUTH-03 — SECURE AUTHENTICATION & SESSION CLOSED
```

Do not automatically open provisioning, business authorization, forecast ownership, or ML phases.

---

## Microiteration Commit/Push Governance

Each `03-A…03-J` candidate follows the same release discipline:

```text
published input baseline
      ↓
guard guards
      ↓
RED
      ↓
minimal implementation
      ↓
focused GREEN
      ↓
regression
      ↓
quality/boundary/scope audit
      ↓
Architectural Gate
      ↓
exact staging
      ↓
controlled local commit
      ↓
post-commit verification
      ↓
controlled push
      ↓
HEAD == origin/main
      ↓
new baseline freeze
      ↓
MANDATORY STOP
```

Never stage before the Gate unless the specific Gate contract explicitly authorizes staging.

Never combine two microiterations into one commit.

---

## Planned Commit Messages

Use these only after the corresponding Gate authorizes commit:

```text
docs: add NF-AUTH-03 secure authentication design
docs: add NF-AUTH-03 implementation plan

feat: add Argon2id credential security core
feat: add password credential persistence
feat: add JWT authentication core
feat: add refresh session persistence
feat: issue durable authentication sessions
feat: add atomic refresh rotation
feat: add refresh family logout
feat: add secure browser authentication transport
test: verify integrated authentication security
```

`03-J` independent QA does not create a source commit.

Corrective microiterations, if required, receive their own descriptive commit after their own Gate.

---

## Final Scope-Negative Audit

Before `NF-AUTH-03` closure, confirm the repository did not accidentally introduce:

```text
public signup                              0
public registration                        0
invite/provisioning endpoint               0
password reset/recovery/change endpoint    0
MFA                                        0
OAuth/OIDC/SSO                             0
account lockout/CAPTCHA/rate limiting      0
account_status model                       0
logout-all                                 0
access-token denylist                      0
JWKS/dynamic remote key discovery          0
refresh grace window                       0
cross-site production auth design          0
device fingerprint/IP/geo binding          0
forecast ownership/authorization           0
ADMIN exceptional access                   0
/auth/me incidental endpoint               0
ML artifact changes                        0
```

Any nonzero result requires explicit architectural review.

---

## Execution Handoff

This plan is written for task-by-task execution with review checkpoints.

Recommended execution mode after the Documentation Gate:

1. **Subagent-Driven Development** — one fresh agent per microiteration, with contract review and verification before each next Gate.
2. **Inline Execution** — execute through `executing-plans` in bounded batches, preserving every explicit STOP.

No execution mode may bypass `03-A…03-J` Gates or the Docker/PostgreSQL preconditions.

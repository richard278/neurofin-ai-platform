# NF-AUTH-02 Identity Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and independently verify NeuroFin's first persistent `User` identity model without introducing provisioning, passwords, login, JWT, refresh sessions, authorization, ownership, frontend changes, or forecast persistence.

**Architecture:** Keep `User`, `UserRole`, email invariants, the async `UserRepository` port, and semantic repository exceptions in Domain. Keep SQLAlchemy `Base`, `UserModel`, explicit mapping, `SQLAlchemyUserRepository`, `AsyncSession`, PostgreSQL details, and Alembic metadata in Infrastructure; repositories flush but do not own commit/rollback/session lifecycle.

**Tech Stack:** Python 3.11, dataclasses, `StrEnum`, UUID, pytest, SQLAlchemy 2.0.x async, asyncpg, Alembic 1.19.x, PostgreSQL 18.4, Docker Compose, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-24-nf-auth-02-identity-persistence-design.md`

## Global Constraints

- Baseline before implementation: `dd7b78062b3521fcc94714fa022f190b65912ef9`.
- Python runtime: `>=3.11`; Ruff target: `py311`; mypy Python: `3.11`.
- PostgreSQL is the primary persistence engine; SQLite may not substitute for PostgreSQL-specific verification.
- SQLAlchemy remains `>=2.0.52,<2.1.0`; asyncpg remains `>=0.31.0,<1.0.0`; Alembic remains `>=1.19.0,<2.0.0`.
- Domain and Application must not import FastAPI, Pydantic, SQLAlchemy, `AsyncSession`, asyncpg, PostgreSQL, or Alembic.
- Final repository port methods are exactly `add(User)`, `get_by_id(UUID)`, and `get_by_email(canonical_email)`, all async.
- `User` is immutable; UUID is generated before persistence; PostgreSQL has no UUID server default.
- Email canonicalization is outer `strip()` + lowercase + the exact ASCII profile in the spec.
- Database email validation is defense-in-depth only: `email = lower(btrim(email))`.
- PostgreSQL role storage is text `ANALYST|ADMIN`, `NOT NULL`, with no default and no native PostgreSQL ENUM.
- `SQLAlchemyUserRepository` receives an existing `AsyncSession`; it may `flush()` but may not `begin()`, `commit()`, `rollback()`, `close()`, canonicalize, generate UUIDs, or assign roles.
- `uq_users_email` and `pk_users` both translate to `UserAlreadyExistsError` using structured driver/PostgreSQL metadata, never human-readable-message parsing.
- `SEC-Q02` provisioning remains open; `User.create()` is not provisioning.
- No password hashes, Argon2id, signup, provisioning, login, JWT, refresh, sessions, account status, role mutation, forecast ownership, frontend work, Unit of Work, forecast persistence, or ML persistence.
- Every microiteration ends at an explicit STOP. Approval of one task does not authorize the next.
- Use TDD: demonstrate RED before implementation and GREEN after the minimal implementation.
- Known baseline Ruff/mypy debt may remain; new debt attributable to NF-AUTH-02 must be zero.

---

## File Structure Map

### Existing files to modify

- `backend/alembic/env.py` — switch Alembic from `target_metadata = None` to the Infrastructure `Base.metadata` and register `UserModel`.
- `backend/tests/test_alembic_foundation.py` — preserve baseline-revision checks while updating assertions for a new functional head.

### New Domain files

- `backend/app/domain/entities/user.py` — `UserRole`, `User`, `InvalidUserEmailError`, canonicalization/validation.
- `backend/app/domain/repositories/user_repository.py` — async `UserRepository`, `UserRepositoryError`, `UserAlreadyExistsError`.
- `backend/tests/test_user_domain.py` — pure Domain contract tests.

### New Infrastructure ORM/mapping files

- `backend/app/infrastructure/database/base.py` — sole declarative `Base`.
- `backend/app/infrastructure/database/models/__init__.py` — model package export.
- `backend/app/infrastructure/database/models/user.py` — `UserModel` and exact physical constraints.
- `backend/app/infrastructure/database/mappers/__init__.py` — mapper package.
- `backend/app/infrastructure/database/mappers/user_mapper.py` — pure `User <-> UserModel` conversion.
- `backend/tests/test_user_orm_mapping.py` — metadata and pure mapper tests.

### New migration/integration files

- `backend/alembic/versions/20260824a001_create_users.py` — first functional migration; `down_revision = "116464527395"`.
- `backend/tests/integration/test_user_schema_postgres.py` — real PostgreSQL Alembic/schema/constraint verification.

### New repository files

- `backend/app/infrastructure/repositories/sqlalchemy_user_repository.py` — thin async adapter and structured error translation.
- `backend/tests/test_sqlalchemy_user_repository.py` — isolated adapter behavior/error-translation tests.
- `backend/tests/integration/test_user_repository_postgres.py` — real PostgreSQL repository/transaction behavior.

No other production paths are planned.

---

## Pre-Execution Documentation Gate

The approved specification and this plan must exist in the local repository before code work begins.

Expected paths:

```text
docs/superpowers/specs/2026-08-24-nf-auth-02-identity-persistence-design.md
docs/superpowers/plans/2026-08-24-nf-auth-02-identity-persistence-implementation-plan.md
```

Because the ChatGPT GitHub connector could not write these files (`403`), the executing worker must treat their local placement as a documentation precondition, not as feature implementation.

- [ ] Confirm the repository is `richard278/neurofin-ai-platform`, branch is `main`, and `git rev-parse HEAD` equals `dd7b78062b3521fcc94714fa022f190b65912ef9`.
- [ ] Confirm `git status --short` is clean before placing documentation. If it is not clean, STOP without reset/stash/clean.
- [ ] Place the already approved spec and plan at the exact paths above.
- [ ] Run `git diff --check` and inspect the documentation-only diff.
- [ ] Commit the spec first with `git commit -m "docs: add NF-AUTH-02 identity persistence design"`.
- [ ] Commit the plan with `git commit -m "docs: add NF-AUTH-02 implementation plan"`.
- [ ] Confirm `git status --short` is clean and record the resulting documentation baseline.
- [ ] STOP for architectural confirmation before Task 1.

---

### Task 1: NF-AUTH-02-A — Domain Identity

**Files:**
- Create: `backend/app/domain/entities/user.py`
- Create: `backend/app/domain/repositories/user_repository.py`
- Create: `backend/tests/test_user_domain.py`

**Interfaces:**
- Produces: `UserRole.ANALYST`, `UserRole.ADMIN`, `InvalidUserEmailError`, `User.create(raw_email: str, role: UserRole) -> User`, strict `User(id: UUID, email: str, role: UserRole)`, async `UserRepository.add/get_by_id/get_by_email`, `UserRepositoryError`, `UserAlreadyExistsError`.
- Consumes: Python stdlib only in Domain (`abc`, `dataclasses`, `enum`, `uuid`).

- [ ] **Step 1: Add pure Domain tests first**

Create `backend/tests/test_user_domain.py` with the following contract:

```python
from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest

from app.domain.entities.user import InvalidUserEmailError, User, UserRole
from app.domain.repositories.user_repository import (
    UserAlreadyExistsError,
    UserRepository,
    UserRepositoryError,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Richard@Example.COM", "richard@example.com"),
        ("  Richard.Milian+lab@Example.COM  ", "richard.milian+lab@example.com"),
        ("r_milian@sub.example.com", "r_milian@sub.example.com"),
    ],
)
def test_user_create_canonicalizes_valid_email(raw: str, expected: str) -> None:
    user = User.create(raw, UserRole.ANALYST)

    assert isinstance(user.id, UUID)
    assert user.email == expected
    assert user.role is UserRole.ANALYST


@pytest.mark.parametrize(
    "email",
    [
        "user@localhost",
        "user@@example.com",
        ".user@example.com",
        "user.@example.com",
        "user..name@example.com",
        "user@-example.com",
        "user@example-.com",
        "user@example..com",
        "üser@example.com",
        "\"user name\"@example.com",
        "user@[127.0.0.1]",
        "user name@example.com",
        "user\n@example.com",
        f"{'a' * 65}@example.com",
        f"{'a' * 64}@{'b' * 63}.{'c' * 63}.{'d' * 61}.com",
    ],
)
def test_user_create_rejects_invalid_email(email: str) -> None:
    with pytest.raises(InvalidUserEmailError):
        User.create(email, UserRole.ANALYST)


def test_user_constructor_rejects_noncanonical_persisted_email() -> None:
    with pytest.raises(InvalidUserEmailError):
        User(id=uuid4(), email="Richard@Example.COM", role=UserRole.ANALYST)


def test_user_constructor_rejects_wrong_id_type() -> None:
    with pytest.raises(TypeError, match="id must be UUID"):
        User(id="not-a-uuid", email="user@example.com", role=UserRole.ANALYST)  # type: ignore[arg-type]


def test_user_constructor_rejects_wrong_role_type() -> None:
    with pytest.raises(TypeError, match="role must be UserRole"):
        User(id=uuid4(), email="user@example.com", role="ADMIN")  # type: ignore[arg-type]


def test_user_is_frozen() -> None:
    user = User.create("user@example.com", UserRole.ANALYST)

    with pytest.raises(FrozenInstanceError):
        user.email = "other@example.com"  # type: ignore[misc]


def test_user_role_values_are_exact() -> None:
    assert UserRole.ANALYST.value == "ANALYST"
    assert UserRole.ADMIN.value == "ADMIN"

    with pytest.raises(ValueError):
        UserRole("SUPERADMIN")


def test_repository_errors_are_persistence_agnostic() -> None:
    assert issubclass(UserAlreadyExistsError, UserRepositoryError)
    assert UserRepository.__module__ == "app.domain.repositories.user_repository"
```

- [ ] **Step 2: Run the Domain tests and confirm RED**

Run from `backend/`:

```bash
pytest tests/test_user_domain.py -v
```

Expected: collection/import failure because `user.py` and `user_repository.py` do not exist.

- [ ] **Step 3: Implement the minimal Domain email/entity contract**

Create `backend/app/domain/entities/user.py`:

```python
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
```

- [ ] **Step 4: Implement the final async Domain repository port**

Create `backend/app/domain/repositories/user_repository.py`:

```python
from abc import ABC, abstractmethod
from uuid import UUID

from ..entities.user import User


class UserRepositoryError(RuntimeError):
    pass


class UserAlreadyExistsError(UserRepositoryError):
    pass


class UserRepository(ABC):
    @abstractmethod
    async def add(self, user: User) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError
```

- [ ] **Step 5: Run Domain tests and confirm GREEN**

```bash
pytest tests/test_user_domain.py -v
```

Expected: all tests in `test_user_domain.py` PASS.

- [ ] **Step 6: Run regression and focused static checks**

```bash
pytest -q
ruff check app/domain/entities/user.py app/domain/repositories/user_repository.py tests/test_user_domain.py
mypy app/domain/entities/user.py app/domain/repositories/user_repository.py
git diff --check
```

Expected:
- ordinary suite PASS with PostgreSQL integration tests skipped by default;
- focused Ruff PASS;
- focused mypy PASS;
- `git diff --check` PASS.

- [ ] **Step 7: Verify the A-scope boundary**

```bash
git diff --name-only
git grep -n -E "sqlalchemy|asyncpg|alembic|fastapi|pydantic" -- \
  backend/app/domain/entities/user.py \
  backend/app/domain/repositories/user_repository.py
```

Expected:
- only the three A paths are changed/created;
- the grep returns no Domain framework/persistence imports.

- [ ] **Step 8: STOP and request architectural Gate A**

Do not stage or commit until the Gate is approved.

- [ ] **Step 9: After Gate A approval, commit only Task 1**

```bash
git add \
  backend/app/domain/entities/user.py \
  backend/app/domain/repositories/user_repository.py \
  backend/tests/test_user_domain.py

git diff --cached --check
git diff --cached --name-only
git commit -m "feat: add user domain identity"
```

Expected staged cardinality: 3 paths.

- [ ] **Step 10: Synchronize only after explicit release approval**

Push the approved commit to `origin/main`, confirm `HEAD == origin/main`, record the new baseline, and STOP. Do not start Task 2 automatically.

---

### Task 2: NF-AUTH-02-B — ORM Model and Explicit Mapping

**Files:**
- Create: `backend/app/infrastructure/database/base.py`
- Create: `backend/app/infrastructure/database/models/__init__.py`
- Create: `backend/app/infrastructure/database/models/user.py`
- Create: `backend/app/infrastructure/database/mappers/__init__.py`
- Create: `backend/app/infrastructure/database/mappers/user_mapper.py`
- Create: `backend/tests/test_user_orm_mapping.py`

**Interfaces:**
- Consumes: `User`, `UserRole`.
- Produces: sole Infrastructure `Base`, `UserModel`, `user_to_model(user: User) -> UserModel`, `user_to_domain(model: UserModel) -> User`.
- Does not produce migration/repository behavior.

- [ ] **Step 1: Write failing ORM/mapping tests**

Create `backend/tests/test_user_orm_mapping.py`:

```python
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.domain.entities.user import InvalidUserEmailError, User, UserRole
from app.infrastructure.database.base import Base
from app.infrastructure.database.mappers.user_mapper import user_to_domain, user_to_model
from app.infrastructure.database.models.user import UserModel


def test_user_model_metadata_matches_contract() -> None:
    table = UserModel.__table__

    assert table.metadata is Base.metadata
    assert table.name == "users"
    assert set(table.columns.keys()) == {"id", "email", "role"}

    id_column = table.c.id
    email_column = table.c.email
    role_column = table.c.role

    assert isinstance(id_column.type, PGUUID)
    assert id_column.nullable is False
    assert id_column.server_default is None

    assert isinstance(email_column.type, String)
    assert email_column.type.length == 254
    assert email_column.nullable is False

    assert isinstance(role_column.type, String)
    assert role_column.type.length == 16
    assert role_column.nullable is False
    assert role_column.server_default is None

    constraints = {constraint.name: constraint for constraint in table.constraints}
    assert isinstance(constraints["pk_users"], PrimaryKeyConstraint)
    assert isinstance(constraints["uq_users_email"], UniqueConstraint)
    assert isinstance(constraints["ck_users_email_canonical"], CheckConstraint)
    assert isinstance(constraints["ck_users_role"], CheckConstraint)


@pytest.mark.parametrize("role", [UserRole.ANALYST, UserRole.ADMIN])
def test_mapper_round_trip_preserves_identity(role: UserRole) -> None:
    user = User(id=uuid4(), email="user@example.com", role=role)

    model = user_to_model(user)
    restored = user_to_domain(model)

    assert model.id == user.id
    assert model.email == user.email
    assert model.role == role.value
    assert restored == user


def test_user_to_domain_rejects_unknown_persisted_role() -> None:
    model = UserModel(id=uuid4(), email="user@example.com", role="SUPERADMIN")

    with pytest.raises(ValueError):
        user_to_domain(model)


def test_user_to_domain_rejects_noncanonical_persisted_email() -> None:
    model = UserModel(id=uuid4(), email="User@Example.COM", role="ANALYST")

    with pytest.raises(InvalidUserEmailError):
        user_to_domain(model)
```

- [ ] **Step 2: Run the new test and confirm RED**

```bash
pytest tests/test_user_orm_mapping.py -v
```

Expected: import failure because `base.py`, `models/user.py`, and mapper files do not exist.

- [ ] **Step 3: Add the sole Infrastructure declarative Base**

Create `backend/app/infrastructure/database/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 4: Add the exact `UserModel` physical declaration**

Create `backend/app/infrastructure/database/models/user.py`:

```python
from uuid import UUID

from sqlalchemy import CheckConstraint, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_users"),
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint(
            "email = lower(btrim(email))",
            name="ck_users_email_canonical",
        ),
        CheckConstraint(
            "role IN ('ANALYST', 'ADMIN')",
            name="ck_users_role",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
```

Create `backend/app/infrastructure/database/models/__init__.py`:

```python
from .user import UserModel

__all__ = ["UserModel"]
```

- [ ] **Step 5: Add pure mapping functions**

Create `backend/app/infrastructure/database/mappers/user_mapper.py`:

```python
from app.domain.entities.user import User, UserRole

from ..models.user import UserModel


def user_to_model(user: User) -> UserModel:
    return UserModel(
        id=user.id,
        email=user.email,
        role=user.role.value,
    )


def user_to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        role=UserRole(model.role),
    )
```

Create `backend/app/infrastructure/database/mappers/__init__.py`:

```python
from .user_mapper import user_to_domain, user_to_model

__all__ = ["user_to_domain", "user_to_model"]
```

- [ ] **Step 6: Run ORM/mapping tests and confirm GREEN**

```bash
pytest tests/test_user_orm_mapping.py -v
```

Expected: PASS.

- [ ] **Step 7: Prove no DB I/O was introduced**

```bash
pytest tests/test_user_domain.py tests/test_user_orm_mapping.py -v
ruff check \
  app/infrastructure/database/base.py \
  app/infrastructure/database/models \
  app/infrastructure/database/mappers \
  tests/test_user_orm_mapping.py
mypy \
  app/infrastructure/database/base.py \
  app/infrastructure/database/models \
  app/infrastructure/database/mappers
git diff --check
```

Expected: PASS.

- [ ] **Step 8: Verify exact B scope**

```bash
git diff --name-only
git grep -n -E "session|execute|commit|rollback|flush" -- \
  backend/app/infrastructure/database/mappers
```

Expected:
- only Task 2 paths are changed relative to its input baseline;
- mapper package contains no DB/session/transaction behavior.

- [ ] **Step 9: STOP for Gate B**

No Alembic edits, migration creation, repository adapter, staging, or commit before review.

- [ ] **Step 10: After Gate B approval, commit exactly Task 2**

```bash
git add \
  backend/app/infrastructure/database/base.py \
  backend/app/infrastructure/database/models/__init__.py \
  backend/app/infrastructure/database/models/user.py \
  backend/app/infrastructure/database/mappers/__init__.py \
  backend/app/infrastructure/database/mappers/user_mapper.py \
  backend/tests/test_user_orm_mapping.py

git diff --cached --check
git commit -m "feat: add user ORM mapping"
```

Then synchronize only after explicit release approval, record the baseline, and STOP.

---

### Task 3: NF-AUTH-02-C — Users Alembic Migration and Real PostgreSQL Schema Gate

**Files:**
- Modify: `backend/alembic/env.py`
- Modify: `backend/tests/test_alembic_foundation.py`
- Create: `backend/alembic/versions/20260824a001_create_users.py`
- Create: `backend/tests/integration/test_user_schema_postgres.py`

**Interfaces:**
- Consumes: `Base.metadata`, registered `UserModel`, existing Alembic baseline `116464527395`, existing PostgreSQL Compose infrastructure.
- Produces: functional Alembic head `20260824a001`, physical `users` table contract, migration/schema evidence.
- Does not produce repository behavior.

- [ ] **Step 1: Update tests first for the new Alembic graph and metadata expectation**

In `backend/tests/test_alembic_foundation.py`:
- retain `test_alembic_ini_exists_and_loads`, `test_script_directory_resolves`, `test_single_base_revision`, `test_single_head_revision`;
- change the old base=head expectations to the following tests:

```python
def test_baseline_revision_remains_root() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)

    bases = script.get_bases()
    assert bases == ["116464527395"]

    base_rev = script.get_revision("116464527395")
    assert base_rev is not None
    assert base_rev.down_revision is None


def test_auth_head_descends_from_baseline() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260824a001"]

    head_rev = script.get_revision("20260824a001")
    assert head_rev is not None
    assert head_rev.down_revision == "116464527395"


def test_env_py_uses_infrastructure_metadata() -> None:
    env_path = Path(__file__).parent.parent / "alembic" / "env.py"
    source = env_path.read_text(encoding="utf-8")

    assert "from app.infrastructure.database.base import Base" in source
    assert "from app.infrastructure.database.models.user import UserModel" in source
    assert "target_metadata = Base.metadata" in source
```

Modify `test_baseline_revision_no_ddl_operations()` so it reads revision `116464527395` explicitly instead of the head.

- [ ] **Step 2: Add a failing real-PostgreSQL schema test file**

Create `backend/tests/integration/test_user_schema_postgres.py`:

```python
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.infrastructure.database.engine import create_database_engine
from app.infrastructure.database.session import create_session_factory

RUN_INTEGRATION = os.environ.get("NEUROFIN_RUN_POSTGRES_INTEGRATION") == "1"

pytestmark = [
    pytest.mark.postgres_integration,
    pytest.mark.skipif(
        not RUN_INTEGRATION,
        reason="NEUROFIN_RUN_POSTGRES_INTEGRATION != '1'.",
    ),
]

BACKEND_DIR = Path(__file__).parents[2]


def _run_alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        check=True,
    )


@pytest.mark.asyncio
async def test_users_schema_matches_contract() -> None:
    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    async with factory() as session:
        table_rows = await session.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
        )
        assert [row[0] for row in table_rows] == ["alembic_version", "users"]

        column_rows = await session.execute(
            text(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users'
                ORDER BY ordinal_position
                """
            )
        )
        assert list(column_rows) == [
            ("id", "uuid", "NO", None),
            ("email", "character varying", "NO", None),
            ("role", "character varying", "NO", None),
        ]

        constraint_rows = await session.execute(
            text(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'public.users'::regclass
                ORDER BY conname
                """
            )
        )
        assert {row[0] for row in constraint_rows} == {
            "ck_users_email_canonical",
            "ck_users_role",
            "pk_users",
            "uq_users_email",
        }

    await engine.dispose()


def test_users_migration_round_trip() -> None:
    _run_alembic("upgrade", "head")
    _run_alembic("downgrade", "116464527395")
    _run_alembic("upgrade", "head")
```

- [ ] **Step 3: Run structural tests and confirm RED**

```bash
pytest tests/test_alembic_foundation.py -v
```

Expected: FAIL because the current head is still `116464527395` and `target_metadata` is still `None`.

- [ ] **Step 4: Connect Alembic to Infrastructure metadata**

Modify `backend/alembic/env.py` near the imports:

```python
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.user import UserModel

_ = UserModel
target_metadata = Base.metadata
```

Remove the old `target_metadata = None`.

Do not change URL loading, async engine setup, `NullPool`, or migration lifecycle.

- [ ] **Step 5: Generate the migration draft with a deterministic revision ID**

With a disposable PostgreSQL instance available and `DATABASE_URL` configured, run from `backend/`:

```bash
python -m alembic revision \
  --autogenerate \
  --rev-id 20260824a001 \
  -m "create users"
```

Expected file: `alembic/versions/20260824a001_create_users.py`.

- [ ] **Step 6: Manually review and normalize the migration to the exact approved DDL**

The final migration must be equivalent to:

```python
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260824a001"
down_revision: str | Sequence[str] | None = "116464527395"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "email = lower(btrim(email))",
            name="ck_users_email_canonical",
        ),
        sa.CheckConstraint(
            "role IN ('ANALYST', 'ADMIN')",
            name="ck_users_role",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )


def downgrade() -> None:
    op.drop_table("users")
```

No indexes, timestamps, defaults, passwords, status, session tables, forecast tables, or other DDL.

- [ ] **Step 7: Start the disposable PostgreSQL 18.4 environment**

From repository root:

```bash
export NF_PG_USER=neurofin_nf_auth_02
export NF_PG_PASSWORD=neurofin_nf_auth_02_local
export NF_PG_DATABASE=neurofin_nf_auth_02
export NF_PG_PORT=55432
export DATABASE_URL="postgresql+asyncpg://${NF_PG_USER}:${NF_PG_PASSWORD}@127.0.0.1:${NF_PG_PORT}/${NF_PG_DATABASE}"
export NEUROFIN_DATABASE_URL="$DATABASE_URL"
export NEUROFIN_RUN_POSTGRES_INTEGRATION=1

docker compose -f infra/postgres/compose.yml up -d
docker compose -f infra/postgres/compose.yml ps
```

Wait until the Compose healthcheck reports PostgreSQL healthy.

- [ ] **Step 8: Run the real migration/schema tests**

From `backend/` with the environment above:

```bash
pytest tests/test_alembic_foundation.py -v
pytest tests/integration/test_user_schema_postgres.py -v
```

Expected: PASS.

- [ ] **Step 9: Add direct constraint-defense tests**

Append to `test_user_schema_postgres.py`:

```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "role"),
    [
        ("User@example.com", "ANALYST"),
        (" user@example.com ", "ANALYST"),
        ("user@example.com", "SUPERADMIN"),
    ],
)
async def test_database_rejects_invalid_persisted_identity(email: str, role: str) -> None:
    from uuid import uuid4

    from sqlalchemy.exc import IntegrityError

    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    async with factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO users (id, email, role)
                    VALUES (:id, :email, :role)
                    """
                ),
                {"id": uuid4(), "email": email, "role": role},
            )
            await session.flush()
        await session.rollback()

    await engine.dispose()
```

Append this duplicate canonical-email test:

```python
@pytest.mark.asyncio
async def test_database_rejects_duplicate_canonical_email() -> None:
    from uuid import uuid4

    from sqlalchemy.exc import IntegrityError

    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO users (id, email, role)
                VALUES (:id, :email, :role)
                """
            ),
            {
                "id": uuid4(),
                "email": "duplicate@example.com",
                "role": "ANALYST",
            },
        )
        await session.commit()

    async with factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO users (id, email, role)
                    VALUES (:id, :email, :role)
                    """
                ),
                {
                    "id": uuid4(),
                    "email": "duplicate@example.com",
                    "role": "ADMIN",
                },
            )
            await session.flush()
        await session.rollback()

    await engine.dispose()
```

- [ ] **Step 10: Run complete C verification**

```bash
pytest tests/test_alembic_foundation.py tests/test_user_orm_mapping.py -v
pytest tests/integration/test_user_schema_postgres.py -v
pytest -q
ruff check alembic/env.py alembic/versions/20260824a001_create_users.py tests/test_alembic_foundation.py tests/integration/test_user_schema_postgres.py
git diff --check
```

Expected:
- real PostgreSQL schema and round-trip PASS;
- ordinary regression PASS;
- focused Ruff PASS;
- no new business table other than `users`.

- [ ] **Step 11: Clean disposable PostgreSQL resources**

From repository root:

```bash
docker compose -f infra/postgres/compose.yml down -v
docker compose -f infra/postgres/compose.yml ps -a
```

Expected: no project container or named volume remains.

- [ ] **Step 12: STOP for Gate C**

Do not create the repository adapter.

- [ ] **Step 13: After Gate C approval, commit exactly C paths**

```bash
git add \
  backend/alembic/env.py \
  backend/alembic/versions/20260824a001_create_users.py \
  backend/tests/test_alembic_foundation.py \
  backend/tests/integration/test_user_schema_postgres.py

git diff --cached --check
git commit -m "feat: add user identity migration"
```

Synchronize only after explicit release approval, record the baseline, and STOP.

---

### Task 4: NF-AUTH-02-D — `SQLAlchemyUserRepository` Adapter

**Files:**
- Create: `backend/app/infrastructure/repositories/sqlalchemy_user_repository.py`
- Create: `backend/tests/test_sqlalchemy_user_repository.py`

**Interfaces:**
- Consumes: `UserRepository`, `UserRepositoryError`, `UserAlreadyExistsError`, `UserModel`, mapper functions, injected `AsyncSession`.
- Produces: `SQLAlchemyUserRepository(session: AsyncSession)` with exactly `add`, `get_by_id`, `get_by_email`.
- Transaction ownership remains external.

- [ ] **Step 1: Write isolated repository tests first**

Create `backend/tests/test_sqlalchemy_user_repository.py`:

```python
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User, UserRole
from app.domain.repositories.user_repository import (
    UserAlreadyExistsError,
    UserRepositoryError,
)
from app.infrastructure.database.models.user import UserModel
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)


class StructuredDriverError(Exception):
    def __init__(self, sqlstate: str, constraint_name: str) -> None:
        super().__init__("structured driver error")
        self.sqlstate = sqlstate
        self.constraint_name = constraint_name


def _session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_add_uses_add_and_flush_without_commit_or_rollback() -> None:
    session = _session()
    repository = SQLAlchemyUserRepository(session)
    user = User.create("user@example.com", UserRole.ANALYST)

    await repository.add(user)

    session.add.assert_called_once()
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    session.close.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("constraint_name", ["uq_users_email", "pk_users"])
async def test_identity_unique_constraints_translate_to_user_already_exists(
    constraint_name: str,
) -> None:
    session = _session()
    session.flush.side_effect = IntegrityError(
        "INSERT INTO users ...",
        {},
        StructuredDriverError("23505", constraint_name),
    )
    repository = SQLAlchemyUserRepository(session)
    user = User.create("user@example.com", UserRole.ANALYST)

    with pytest.raises(UserAlreadyExistsError) as exc_info:
        await repository.add(user)

    assert isinstance(exc_info.value.__cause__, IntegrityError)
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_integrity_constraint_is_generic_repository_error() -> None:
    session = _session()
    session.flush.side_effect = IntegrityError(
        "INSERT INTO users ...",
        {},
        StructuredDriverError("23514", "ck_users_role"),
    )
    repository = SQLAlchemyUserRepository(session)
    user = User.create("user@example.com", UserRole.ANALYST)

    with pytest.raises(UserRepositoryError) as exc_info:
        await repository.add(user)

    assert type(exc_info.value) is UserRepositoryError
    assert isinstance(exc_info.value.__cause__, IntegrityError)


@pytest.mark.asyncio
async def test_get_by_id_maps_model_to_domain() -> None:
    session = _session()
    user_id = uuid4()
    session.get.return_value = UserModel(
        id=user_id,
        email="user@example.com",
        role="ANALYST",
    )
    repository = SQLAlchemyUserRepository(session)

    user = await repository.get_by_id(user_id)

    assert user == User(id=user_id, email="user@example.com", role=UserRole.ANALYST)


@pytest.mark.asyncio
async def test_get_by_id_missing_returns_none() -> None:
    session = _session()
    session.get.return_value = None
    repository = SQLAlchemyUserRepository(session)

    assert await repository.get_by_id(uuid4()) is None


@pytest.mark.asyncio
async def test_get_by_email_executes_exact_query_and_maps_result() -> None:
    session = _session()
    result = MagicMock()
    result.scalar_one_or_none.return_value = UserModel(
        id=uuid4(),
        email="user@example.com",
        role="ADMIN",
    )
    session.execute.return_value = result
    repository = SQLAlchemyUserRepository(session)

    user = await repository.get_by_email("user@example.com")

    session.execute.assert_awaited_once()
    assert user is not None
    assert user.email == "user@example.com"
    assert user.role is UserRole.ADMIN


@pytest.mark.asyncio
async def test_sqlalchemy_query_failure_translates_to_repository_error() -> None:
    session = _session()
    session.get.side_effect = SQLAlchemyError("database unavailable")
    repository = SQLAlchemyUserRepository(session)

    with pytest.raises(UserRepositoryError) as exc_info:
        await repository.get_by_id(uuid4())

    assert isinstance(exc_info.value.__cause__, SQLAlchemyError)
```

- [ ] **Step 2: Run isolated repository tests and confirm RED**

```bash
pytest tests/test_sqlalchemy_user_repository.py -v
```

Expected: import failure because the adapter does not exist.

- [ ] **Step 3: Implement the thin adapter and structured metadata walker**

Create `backend/app/infrastructure/repositories/sqlalchemy_user_repository.py`:

```python
from collections.abc import Iterator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.domain.repositories.user_repository import (
    UserAlreadyExistsError,
    UserRepository,
    UserRepositoryError,
)
from app.infrastructure.database.mappers.user_mapper import user_to_domain, user_to_model
from app.infrastructure.database.models.user import UserModel

_IDENTITY_UNIQUE_CONSTRAINTS = {"pk_users", "uq_users_email"}


def _exception_chain(exc: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = exc

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current

        orig = getattr(current, "orig", None)
        if isinstance(orig, BaseException) and id(orig) not in seen:
            current = orig
            continue

        cause = current.__cause__
        if cause is not None and id(cause) not in seen:
            current = cause
            continue

        context = current.__context__
        if context is not None and id(context) not in seen:
            current = context
            continue

        current = None


def _structured_postgres_identity_conflict(exc: IntegrityError) -> bool:
    for candidate in _exception_chain(exc):
        sqlstate = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)

        constraint_name = getattr(candidate, "constraint_name", None)
        diag = getattr(candidate, "diag", None)
        if constraint_name is None and diag is not None:
            constraint_name = getattr(diag, "constraint_name", None)

        if sqlstate == "23505" and constraint_name in _IDENTITY_UNIQUE_CONSTRAINTS:
            return True

    return False


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        model = user_to_model(user)
        try:
            self._session.add(model)
            await self._session.flush()
        except IntegrityError as exc:
            if _structured_postgres_identity_conflict(exc):
                raise UserAlreadyExistsError("user identity already exists") from exc
            raise UserRepositoryError("user persistence failed") from exc
        except SQLAlchemyError as exc:
            raise UserRepositoryError("user persistence failed") from exc

    async def get_by_id(self, user_id: UUID) -> User | None:
        try:
            model = await self._session.get(UserModel, user_id)
        except SQLAlchemyError as exc:
            raise UserRepositoryError("user lookup failed") from exc

        return None if model is None else user_to_domain(model)

    async def get_by_email(self, email: str) -> User | None:
        statement = select(UserModel).where(UserModel.email == email)

        try:
            result = await self._session.execute(statement)
            model = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise UserRepositoryError("user lookup failed") from exc

        return None if model is None else user_to_domain(model)
```

Do not add exports or generic repository abstractions unless required by existing project import conventions.

- [ ] **Step 4: Run isolated repository tests and confirm GREEN**

```bash
pytest tests/test_sqlalchemy_user_repository.py -v
```

Expected: PASS.

- [ ] **Step 5: Verify D contract and no transaction ownership**

```bash
pytest tests/test_user_domain.py tests/test_user_orm_mapping.py tests/test_sqlalchemy_user_repository.py -v
ruff check \
  app/infrastructure/repositories/sqlalchemy_user_repository.py \
  tests/test_sqlalchemy_user_repository.py
mypy app/infrastructure/repositories/sqlalchemy_user_repository.py
git diff --check
```

Expected: PASS.

- [ ] **Step 6: Audit forbidden adapter behavior**

```bash
git grep -n -E "\.commit\(|\.rollback\(|\.close\(|async_sessionmaker|create_session_factory|lower\(|strip\(" -- \
  backend/app/infrastructure/repositories/sqlalchemy_user_repository.py
```

Expected: no forbidden lifecycle/canonicalization/session-factory calls in production adapter code.

- [ ] **Step 7: STOP for Gate D**

Real PostgreSQL error metadata is not yet declared verified. Do not claim that the structured walker works against asyncpg until Task 5.

- [ ] **Step 8: After Gate D approval, commit exactly D paths**

```bash
git add \
  backend/app/infrastructure/repositories/sqlalchemy_user_repository.py \
  backend/tests/test_sqlalchemy_user_repository.py

git diff --cached --check
git commit -m "feat: add SQLAlchemy user repository"
```

Synchronize only after explicit release approval, record the baseline, and STOP.

---

### Task 5: NF-AUTH-02-E — Real PostgreSQL Repository and Transaction Verification

**Files:**
- Create: `backend/tests/integration/test_user_repository_postgres.py`
- Modify only if real evidence proves necessary: `backend/app/infrastructure/repositories/sqlalchemy_user_repository.py`

**Interfaces:**
- Consumes: migrated `users` schema, `SQLAlchemyUserRepository`, session factory, real PostgreSQL 18.4.
- Produces: evidence that repository persistence, reads, transaction ownership, and structured error translation behave as specified.
- New feature behavior is prohibited; any adapter correction must be narrowly justified by a failing real integration test.

- [ ] **Step 1: Create real repository integration tests**

Create `backend/tests/integration/test_user_repository_postgres.py`:

```python
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.core.config import get_settings
from app.domain.entities.user import User, UserRole
from app.domain.repositories.user_repository import UserAlreadyExistsError
from app.infrastructure.database.engine import create_database_engine
from app.infrastructure.database.models.user import UserModel
from app.infrastructure.database.session import create_session_factory
from app.infrastructure.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository

RUN_INTEGRATION = os.environ.get("NEUROFIN_RUN_POSTGRES_INTEGRATION") == "1"

pytestmark = [
    pytest.mark.postgres_integration,
    pytest.mark.skipif(
        not RUN_INTEGRATION,
        reason="NEUROFIN_RUN_POSTGRES_INTEGRATION != '1'.",
    ),
]

BACKEND_DIR = Path(__file__).parents[2]


def _run_alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        check=True,
    )


@pytest_asyncio.fixture
async def database():
    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    async with factory() as cleanup_session:
        await cleanup_session.execute(delete(UserModel))
        await cleanup_session.commit()

    yield engine, factory

    async with factory() as cleanup_session:
        await cleanup_session.execute(delete(UserModel))
        await cleanup_session.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_add_external_commit_and_read_back(database) -> None:
    _, factory = database
    user = User.create("user@example.com", UserRole.ANALYST)

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        await repository.add(user)
        await session.commit()

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        assert await repository.get_by_id(user.id) == user
        assert await repository.get_by_email(user.email) == user
        assert await repository.get_by_id(uuid4()) is None
        assert await repository.get_by_email("missing@example.com") is None


@pytest.mark.asyncio
async def test_get_by_email_does_not_canonicalize(database) -> None:
    _, factory = database
    user = User.create("user@example.com", UserRole.ANALYST)

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        await repository.add(user)
        await session.commit()

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        assert await repository.get_by_email("USER@EXAMPLE.COM") is None


@pytest.mark.asyncio
async def test_flush_does_not_commit_and_external_rollback_removes_insert(database) -> None:
    _, factory = database
    user = User.create("rollback@example.com", UserRole.ANALYST)

    session_a = factory()
    session_b = factory()

    try:
        repository_a = SQLAlchemyUserRepository(session_a)
        await repository_a.add(user)

        repository_b = SQLAlchemyUserRepository(session_b)
        assert await repository_b.get_by_id(user.id) is None

        await session_a.rollback()
    finally:
        await session_a.close()
        await session_b.close()

    async with factory() as session_c:
        repository_c = SQLAlchemyUserRepository(session_c)
        assert await repository_c.get_by_id(user.id) is None


@pytest.mark.asyncio
async def test_duplicate_email_translates_to_user_already_exists(database) -> None:
    _, factory = database
    first = User.create("duplicate@example.com", UserRole.ANALYST)
    second = User.create("duplicate@example.com", UserRole.ADMIN)

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        await repository.add(first)
        await session.commit()

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            await repository.add(second)

        assert exc_info.value.__cause__ is not None
        await session.rollback()


@pytest.mark.asyncio
async def test_duplicate_uuid_translates_to_user_already_exists(database) -> None:
    _, factory = database
    user_id = uuid4()
    first = User(id=user_id, email="first@example.com", role=UserRole.ANALYST)
    second = User(id=user_id, email="second@example.com", role=UserRole.ADMIN)

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        await repository.add(first)
        await session.commit()

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            await repository.add(second)

        assert exc_info.value.__cause__ is not None
        await session.rollback()
```

The fixture uses `@pytest_asyncio.fixture` explicitly so behavior is deterministic under pytest-asyncio strict mode.

- [ ] **Step 2: Start clean PostgreSQL 18.4**

From repository root:

```bash
export NF_PG_USER=neurofin_nf_auth_02
export NF_PG_PASSWORD=neurofin_nf_auth_02_local
export NF_PG_DATABASE=neurofin_nf_auth_02
export NF_PG_PORT=55432
export DATABASE_URL="postgresql+asyncpg://${NF_PG_USER}:${NF_PG_PASSWORD}@127.0.0.1:${NF_PG_PORT}/${NF_PG_DATABASE}"
export NEUROFIN_DATABASE_URL="$DATABASE_URL"
export NEUROFIN_RUN_POSTGRES_INTEGRATION=1

docker compose -f infra/postgres/compose.yml up -d
```

- [ ] **Step 3: Run repository integration tests**

From `backend/`:

```bash
pytest tests/integration/test_user_repository_postgres.py -v
```

Expected: all repository integration tests PASS.

If duplicate-email/UUID tests fail because the actual asyncpg structured metadata is exposed at a different attribute path, keep the failing evidence and proceed only to Step 4. Do not parse `str(exc)`.

- [ ] **Step 4: If real metadata differs, inspect structure without parsing human-readable text**

Use a temporary diagnostic in the failing test or Python debugger to inspect only exception object types and structured attributes:

```python
cause = exc_info.value.__cause__
print(type(cause))
print(type(getattr(cause, "orig", None)))
print(vars(getattr(cause, "orig", None)))
```

If the driver exposes the underlying asyncpg exception through another structured object, minimally adapt `_exception_chain()` to traverse that object. Do not add message-text search.

Then rerun the exact failing integration test until GREEN.

- [ ] **Step 5: Prove failed flush leaves rollback to the outer owner**

Extend one duplicate test:

```python
with pytest.raises(UserAlreadyExistsError):
    await repository.add(second)

assert session.in_transaction()
await session.rollback()
```

Then open a fresh session and assert the first committed user remains and the failed second identity is absent.

- [ ] **Step 6: Run full PostgreSQL semantic Gate**

```bash
pytest \
  tests/integration/test_postgres_infrastructure.py \
  tests/integration/test_user_schema_postgres.py \
  tests/integration/test_user_repository_postgres.py \
  -v

pytest -q
```

Expected:
- infrastructure integration PASS;
- users schema/constraints PASS;
- repository/transaction/error translation PASS;
- full suite PASS with PostgreSQL active.

- [ ] **Step 7: Run focused quality and boundary checks**

```bash
ruff check \
  app/domain/entities/user.py \
  app/domain/repositories/user_repository.py \
  app/infrastructure/database/base.py \
  app/infrastructure/database/models \
  app/infrastructure/database/mappers \
  app/infrastructure/repositories/sqlalchemy_user_repository.py \
  tests/test_user_domain.py \
  tests/test_user_orm_mapping.py \
  tests/test_sqlalchemy_user_repository.py \
  tests/integration/test_user_schema_postgres.py \
  tests/integration/test_user_repository_postgres.py

mypy \
  app/domain/entities/user.py \
  app/domain/repositories/user_repository.py \
  app/infrastructure/database/base.py \
  app/infrastructure/database/models \
  app/infrastructure/database/mappers \
  app/infrastructure/repositories/sqlalchemy_user_repository.py

git diff --check
```

Expected: no new findings in NF-AUTH-02 paths.

- [ ] **Step 8: Stop PostgreSQL and remove disposable resources**

```bash
docker compose -f infra/postgres/compose.yml down -v
docker compose -f infra/postgres/compose.yml ps -a
```

Expected: no residual resources for the project.

- [ ] **Step 9: STOP for Gate E**

Do not add feature code or begin QA closure.

- [ ] **Step 10: After Gate E approval, commit evidence-only tests and any narrowly proven adapter correction**

If adapter code did not change:

```bash
git add backend/tests/integration/test_user_repository_postgres.py
git commit -m "test: verify user repository with PostgreSQL"
```

If a structured-metadata traversal correction was required by real evidence:

```bash
git add \
  backend/app/infrastructure/repositories/sqlalchemy_user_repository.py \
  backend/tests/integration/test_user_repository_postgres.py

git diff --cached --check
git commit -m "test: verify user repository with PostgreSQL"
```

Synchronize only after explicit release approval, record the baseline, and STOP.

---

### Task 6: NF-AUTH-02-F — Independent QA and Final Gate

**Files:**
- Modify: none during QA.
- Evidence: execution report only; if a defect is found, return `NO-GO — CORRECTION REQUIRED` and open a separately authorized remediation microiteration.

**Interfaces:**
- Consumes: published candidate baseline after Task 5.
- Produces: independent closure evidence for `NF-AUTH-02 — IDENTITY PERSISTENCE CLOSED`.
- Source mutation during QA must remain zero.

- [ ] **Step 1: Record candidate baseline and prove the source tree is clean**

```bash
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git status --short --untracked-files=all
```

Expected:
- branch `main`;
- `HEAD == origin/main`;
- clean working tree.

Record the SHA as `NF_AUTH_02_CANDIDATE`.

- [ ] **Step 2: Create a fresh independent clone and Python 3.11 environment**

```bash
QA_ROOT="$(mktemp -d)"
git clone https://github.com/richard278/neurofin-ai-platform.git "$QA_ROOT/neurofin-ai-platform"
cd "$QA_ROOT/neurofin-ai-platform/backend"

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip check
```

Expected: installation and `pip check` PASS.

- [ ] **Step 3: Run ordinary suite with PostgreSQL integration disabled**

```bash
unset NEUROFIN_RUN_POSTGRES_INTEGRATION
pytest -q
```

Expected: all unit/ordinary tests PASS and PostgreSQL-marked tests are controlled SKIP.

- [ ] **Step 4: Verify package boundaries statically**

From fresh `backend/`:

```bash
python - <<'PY'
from pathlib import Path

for root in (Path("app/domain"), Path("app/application")):
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        forbidden = ("sqlalchemy", "asyncpg", "alembic", "AsyncSession")
        found = [token for token in forbidden if token in text]
        if found:
            raise SystemExit(f"{path}: forbidden inward persistence dependency: {found}")

print("PASS: no persistence technology leaked into Domain/Application")
PY
```

Expected: PASS.

- [ ] **Step 5: Run focused NF-AUTH-02 Ruff and mypy**

```bash
ruff check \
  app/domain/entities/user.py \
  app/domain/repositories/user_repository.py \
  app/infrastructure/database/base.py \
  app/infrastructure/database/models \
  app/infrastructure/database/mappers \
  app/infrastructure/repositories/sqlalchemy_user_repository.py \
  tests/test_user_domain.py \
  tests/test_user_orm_mapping.py \
  tests/test_sqlalchemy_user_repository.py \
  tests/integration/test_user_schema_postgres.py \
  tests/integration/test_user_repository_postgres.py

mypy \
  app/domain/entities/user.py \
  app/domain/repositories/user_repository.py \
  app/infrastructure/database/base.py \
  app/infrastructure/database/models \
  app/infrastructure/database/mappers \
  app/infrastructure/repositories/sqlalchemy_user_repository.py
```

Expected: 0 new findings in NF-AUTH-02 files.

Then run full baseline diagnostics:

```bash
ruff check .
mypy app
```

Record any pre-existing findings without modifying source. If the total or locations exceed the documented baseline debt, return NO-GO for analysis.

- [ ] **Step 6: Audit physical scope**

```bash
git diff --name-only dd7b78062b3521fcc94714fa022f190b65912ef9..HEAD
```

Review every path. Expected changes belong only to:
- approved docs;
- Domain user/repository;
- Infrastructure Base/model/mapper/repository;
- Alembic env + one users revision;
- approved tests.

No frontend, forecast implementation, auth endpoint, password, JWT, refresh, ownership, or Unit of Work path is permitted.

- [ ] **Step 7: Run negative capability audit**

```bash
git diff \
  dd7b78062b3521fcc94714fa022f190b65912ef9..HEAD \
  -- backend/app backend/alembic backend/tests \
  | grep -Ei "password_hash|argon2|jwt|refresh_token|signup|provision|change_role|forecast_owner|unitofwork|unit_of_work"
```

Expected: no added implementation of excluded capabilities. Mentions in documentation or explicit negative-scope test comments must be reviewed manually rather than counted as capability.

- [ ] **Step 8: Start fresh PostgreSQL 18.4 for final real Gate**

From fresh repository root:

```bash
cd "$QA_ROOT/neurofin-ai-platform"

export NF_PG_USER=neurofin_nf_auth_02_qa
export NF_PG_PASSWORD=neurofin_nf_auth_02_qa_local
export NF_PG_DATABASE=neurofin_nf_auth_02_qa
export NF_PG_PORT=55432
export DATABASE_URL="postgresql+asyncpg://${NF_PG_USER}:${NF_PG_PASSWORD}@127.0.0.1:${NF_PG_PORT}/${NF_PG_DATABASE}"
export NEUROFIN_DATABASE_URL="$DATABASE_URL"
export NEUROFIN_RUN_POSTGRES_INTEGRATION=1

docker compose -f infra/postgres/compose.yml up -d
docker compose -f infra/postgres/compose.yml ps
```

Wait for healthy status.

- [ ] **Step 9: Execute final Alembic and PostgreSQL verification**

From fresh `backend/`:

```bash
python -m alembic heads
python -m alembic history
python -m alembic upgrade head
python -m alembic downgrade 116464527395
python -m alembic upgrade head

pytest \
  tests/integration/test_postgres_infrastructure.py \
  tests/integration/test_user_schema_postgres.py \
  tests/integration/test_user_repository_postgres.py \
  -v

pytest -q
```

Expected:
- one Alembic head: `20260824a001`;
- upgrade/downgrade/re-upgrade PASS;
- all PostgreSQL integration tests PASS;
- full regression PASS with PostgreSQL active.

- [ ] **Step 10: Audit final PostgreSQL schema directly**

Run:

```bash
python - <<'PY'
import asyncio
from sqlalchemy import text

from app.core.config import get_settings
from app.infrastructure.database.engine import create_database_engine


async def main() -> None:
    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
        )
        tables = [row[0] for row in rows]
        assert tables == ["alembic_version", "users"], tables
    await engine.dispose()


asyncio.run(main())
print("PASS: final business schema contains users only")
PY
```

Expected: PASS.

- [ ] **Step 11: Clean Docker and prove no residual resources**

From fresh repository root:

```bash
docker compose -f infra/postgres/compose.yml down -v
docker compose -f infra/postgres/compose.yml ps -a
```

Expected: no project container/volume remains.

- [ ] **Step 12: Prove QA source mutation is zero**

```bash
git status --short --untracked-files=all
git rev-parse HEAD
```

Expected:
- clean working tree;
- HEAD unchanged from `NF_AUTH_02_CANDIDATE`.

- [ ] **Step 13: Produce the final Gate report**

Report at least:

```text
Candidate SHA
Fresh clone                    PASS/FAIL
Fresh Python 3.11 venv         PASS/FAIL
pip install -e .[dev]          PASS/FAIL
pip check                      PASS/FAIL
Ordinary suite                 PASS/FAIL
Focused Ruff                   PASS/FAIL
Focused mypy                   PASS/FAIL
Known baseline debt            recorded
Domain/Application DB imports  0
Alembic unique head            PASS/FAIL
Upgrade/downgrade/re-upgrade   PASS/FAIL
users physical schema          PASS/FAIL
Named constraints              PASS/FAIL
Real repository add/get        PASS/FAIL
uq_users_email translation     PASS/FAIL
pk_users translation           PASS/FAIL
External rollback              PASS/FAIL
Repository commit ownership    0
Raw SQLAlchemy leakage         0
Scope creep                    0
Secrets introduced             0
QA source mutation             0
Docker residual resources      0
```

Allowed final outcomes only:

```text
GO
GO WITH NON-BLOCKING BASELINE OBSERVATIONS
NO-GO — CORRECTION REQUIRED
```

Do not declare `NF-AUTH-02 — IDENTITY PERSISTENCE CLOSED` unless the fresh QA evidence supports GO or GO WITH NON-BLOCKING BASELINE OBSERVATIONS.

---

## Execution Order and Review Gates

```text
Documentation Gate
      ↓ STOP
Task 1 / AUTH-02-A — Domain Identity
      ↓ Gate A / commit / sync / STOP
Task 2 / AUTH-02-B — ORM + Mapping
      ↓ Gate B / commit / sync / STOP
Task 3 / AUTH-02-C — Users Migration + PostgreSQL schema
      ↓ Gate C / commit / sync / STOP
Task 4 / AUTH-02-D — Repository Adapter
      ↓ Gate D / commit / sync / STOP
Task 5 / AUTH-02-E — Real PostgreSQL Repository Verification
      ↓ Gate E / commit / sync / STOP
Task 6 / AUTH-02-F — Independent QA
      ↓ Final Gate
NF-AUTH-02 — IDENTITY PERSISTENCE CLOSED
```

Implementation workers must not merge adjacent tasks, skip RED/GREEN evidence, or continue past a STOP without explicit architectural authorization.

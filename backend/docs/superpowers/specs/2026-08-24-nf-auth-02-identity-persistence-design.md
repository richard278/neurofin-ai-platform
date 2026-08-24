# NF-AUTH-02 — Identity Persistence Design

**Project:** NeuroFin AI Platform
**Date:** 2026-08-24
**Design status:** APPROVED WITH NON-BLOCKING OBSERVATIONS
**Implementation status:** NOT AUTHORIZED
**Design baseline:** `dd7b78062b3521fcc94714fa022f190b65912ef9`
**Parent foundation:** `NF-DATA-01 — PERSISTENT FOUNDATION CLOSED`
**Security contract:** `NF-SEC-00 — SECURITY DOCUMENTAL BASELINE FROZEN`

---

## 1. Purpose

`NF-AUTH-02` introduces the first functional identity-persistence design in NeuroFin. Its scope is deliberately narrow: define a pure Domain identity, map it to a separate Infrastructure ORM model, persist it through PostgreSQL, expose a minimal async repository port, introduce the first functional Alembic migration, and verify the behavior against real PostgreSQL.

A successful closure of this package means **identity persistence is implemented and independently verified**. It does **not** mean that provisioning, login, JWT, refresh sessions, authorization, ownership, or frontend identity flows are complete.

In particular, closing `NF-AUTH-02` does not close `NF-SEC-03 — Identity / Provisioning`; `SEC-Q02` remains open until the package that actually provisions accounts.

---

## 2. Architectural context

The design starts from the closed `NF-DATA-01` foundation:

- Python 3.11;
- `pyproject.toml` as canonical dependency authority;
- typed PostgreSQL configuration;
- SQLAlchemy 2.x asynchronous infrastructure;
- `AsyncEngine`;
- `async_sessionmaker[AsyncSession]`;
- Alembic baseline revision `116464527395`;
- PostgreSQL 18.4 integration evidence;
- no functional business tables;
- no functional ORM entities.

The current forecast repository remains synchronous and in-memory. `NF-AUTH-02` does not convert it. The first async persistent port is `UserRepository`.

Clean Architecture remains mandatory: Domain and Application do not depend on FastAPI, Pydantic, SQLAlchemy, `AsyncSession`, asyncpg, PostgreSQL, or Alembic.

---

## 3. Scope

### Included

- `User` Domain entity;
- `UserRole` Domain `StrEnum`;
- deterministic email canonicalization and validation;
- `InvalidUserEmailError`;
- async `UserRepository` Domain port;
- persistence-agnostic repository exceptions;
- Infrastructure declarative `Base`;
- Infrastructure `UserModel`;
- explicit `User <-> UserModel` mapper;
- `users` Alembic migration;
- `SQLAlchemyUserRepository`;
- structured persistence-error translation;
- real PostgreSQL integration verification;
- independent QA and final Gate.

### Explicitly excluded

- password hashes or Argon2id implementation;
- signup or account provisioning;
- login;
- JWT or refresh tokens;
- session tables;
- account status;
- role transitions;
- ADMIN management flows;
- forecast ownership;
- frontend changes;
- Unit of Work;
- forecast persistence;
- ML model/version persistence.

No excluded capability may be added as an implementation convenience.

---

## 4. Decision precedence

This specification consolidates `D01–D19` and amendment `D11-A`.

Where historical examples conflict with later approved decisions:

1. **D08 supersedes D07's illustrative `save()` example.** The final port uses `add()`, not `save()`.
2. **D11-A supersedes earlier D16/D18 wording for primary-key collisions.** Both `pk_users` and `uq_users_email` map to `UserAlreadyExistsError`.
3. **D17 is authoritative for exact email syntax.** D04 defines canonicalization policy; D17 defines the practical accepted ASCII profile.
4. **D19 is authoritative for implementation decomposition.** Implementation proceeds only through A–F with STOP after each Gate.

---

## 5. Domain design

### 5.1 `UserRole`

`UserRole` is a pure Domain `StrEnum` with exactly:

```text
ANALYST
ADMIN
```

Conceptually:

```python
class UserRole(StrEnum):
    ANALYST = "ANALYST"
    ADMIN = "ADMIN"
```

Rules:

- no Domain dependency on SQLAlchemy/PostgreSQL;
- unknown roles are invalid;
- no fallback role;
- no implicit role coercion;
- no role-transition methods in this package;
- PostgreSQL stores the role as text, not a native ENUM.

The security posture is fail-closed.

### 5.2 `User`

`User` is an immutable Domain entity:

```python
@dataclass(frozen=True)
class User:
    id: UUID
    email: str
    role: UserRole
```

Strict invariants:

- `id` must already be a `UUID`;
- `role` must already be a valid `UserRole`;
- `email` must already be canonical and satisfy the NeuroFin email profile;
- the constructor does not repair values;
- the constructor does not regenerate UUIDs;
- the constructor does not coerce roles;
- rehydration never silently canonicalizes persisted state.

### 5.3 `User.create()`

`User.create(raw_email, role)` is the factory for a new Domain identity:

```text
raw email
   ↓
outer strip
   ↓
lowercase
   ↓
validate NeuroFin ASCII profile
   ↓
generate uuid4()
   ↓
immutable User
```

Entity creation is not provisioning. The factory does not decide who may create users or what external workflow assigns roles.

---

## 6. Email canonicalization and syntax

### 6.1 Canonical representation

NeuroFin identity emails are application-level case-insensitive identifiers:

- outer `strip()`;
- lowercase;
- syntax validation;
- persist only canonical form;
- PostgreSQL uniqueness on canonical form.

No provider-specific behavior is applied:

- no Gmail dot removal;
- no `+tag` removal;
- no Outlook-specific normalization;
- no provider detection.

### 6.2 Exact accepted profile

NeuroFin accepts a practical explicit ASCII subset, not full RFC 5322.

Full address:

- maximum total length: 254;
- exactly one `@`;
- ASCII only;
- no internal whitespace;
- no control characters.

Local part:

- length 1..64;
- lowercase letters `a-z`;
- digits `0-9`;
- allowed punctuation: `! # $ % & ' * + - / = ? ^ _ ` { | } ~` and `.`;
- no leading dot;
- no trailing dot;
- no consecutive dots.

Domain:

- labels 1..63 characters;
- lowercase letters, digits and `-` only;
- no leading/trailing hyphen;
- no empty labels;
- at least one dot required;
- ASCII punycode allowed if the same label rules hold.

Rejected by design:

- quoted local parts;
- domain literals;
- direct Unicode/SMTPUTF8;
- RFC comments;
- local hostnames such as `user@localhost`;
- DNS/MX/SMTP existence verification.

### 6.3 Domain exception

Email failures use one pure Domain exception:

```python
class InvalidUserEmailError(ValueError):
    ...
```

No Pydantic, SQLAlchemy, asyncpg, PostgreSQL, FastAPI, or external email validator is permitted in Domain.

### 6.4 PostgreSQL defense-in-depth

The database does not duplicate the full Domain parser.

The canonical-form check is deliberately narrower:

```sql
email = lower(btrim(email))
```

This is defense-in-depth for stored representation; it is not a complete equivalent of Python `str.strip()` and is not the full syntax validator.

Authority remains:

```text
Domain     → canonicalization + complete accepted syntax
PostgreSQL → length + NOT NULL + canonical-form defense + uniqueness
```

---

## 7. Domain repository contract

### 7.1 Final async port

```python
class UserRepository(ABC):
    @abstractmethod
    async def add(self, user: User) -> None:
        ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None:
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        ...
```

The port expresses asynchronous I/O without depending on SQLAlchemy.

`ForecastRepository` remains synchronous in this package.

### 7.2 Semantics

`add()` means **insert a new identity** only.

It is not update, merge, save, upsert, replace, or role mutation.

`get_by_id()` retrieves by stable UUID.

`get_by_email()` expects canonical input; Infrastructure does not call `strip()` or `lower()`.

### 7.3 Excluded methods

Do not add `exists_by_email`, listing, delete, update, save, upsert, role mutation, disable, count, pagination, or role searches.

### 7.4 Repository exception hierarchy

```text
UserRepositoryError
    └── UserAlreadyExistsError
```

The exceptions are persistence-agnostic and live near the Domain repository boundary.

`UserAlreadyExistsError` means a proposed identity cannot be inserted because one of its unique identity keys already exists.

---

## 8. Physical PostgreSQL schema

The first functional table is exactly:

```sql
CREATE TABLE users (
    id UUID NOT NULL,
    email VARCHAR(254) NOT NULL,
    role VARCHAR(16) NOT NULL,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_email_canonical CHECK (email = lower(btrim(email))),
    CONSTRAINT ck_users_role CHECK (role IN ('ANALYST', 'ADMIN'))
);
```

Contract:

- `id` is PostgreSQL UUID;
- no DB/server default for UUID;
- UUID is generated before persistence;
- `email VARCHAR(254) NOT NULL UNIQUE`;
- `role VARCHAR(16) NOT NULL`;
- no role default;
- explicit named constraints;
- no PostgreSQL native ENUM.

No extra columns are allowed in this package. Password, status, timestamps, provisioning metadata, and session metadata remain absent.

No default role is permitted because it would become an accidental provisioning policy while `SEC-Q02` remains open.

---

## 9. Infrastructure ORM design

Infrastructure owns one SQLAlchemy declarative `Base`:

```text
app/infrastructure/database/base.py
```

`UserModel` is separate from Domain `User`:

```text
app/infrastructure/database/models/user.py
```

`UserModel` maps exactly to the physical contract. Role is stored as string data; SQLAlchemy Enum is not used.

All ORM models are explicitly registered before Alembic consumes metadata. `Base.metadata` is the sole Alembic metadata source. No second Base is allowed.

---

## 10. Explicit mapping

Mapping is performed by pure Infrastructure functions:

```text
app/infrastructure/database/mappers/user_mapper.py
```

```python
def user_to_model(user: User) -> UserModel:
    ...


def user_to_domain(model: UserModel) -> User:
    ...
```

Domain → ORM is mechanical: exact UUID, exact canonical email, role `.value` to string.

The mapper never canonicalizes, generates UUIDs, executes SQL, uses sessions, handles transactions, catches `IntegrityError`, decides provisioning, or emits HTTP errors.

ORM → Domain is strict:

```text
UserModel
   ↓
UserRole(model.role)
   ↓
User(id=..., email=..., role=...)
```

Invalid persisted role/email fails closed; Infrastructure does not repair invalid persisted values.

---

## 11. Alembic design

Existing baseline revision:

```text
116464527395
```

The first functional auth revision must use it as `down_revision` and create only `users`; downgrade drops only `users`.

### 11.1 `target_metadata`

The current `target_metadata = None` is replaced by Infrastructure `Base.metadata` only when `UserModel` is introduced. Models must be explicitly imported/registered before migration configuration.

### 11.2 Autogenerate policy

Autogenerate is a **draft generator only**:

```text
ORM metadata
   ↓
autogenerate draft
   ↓
manual/architectural review against this spec
   ↓
approved migration
```

Generated output is never accepted automatically.

### 11.3 Reversibility evidence

Required Gate:

```text
baseline
   ↓
upgrade auth revision
   ↓
downgrade baseline
   ↓
upgrade auth revision
```

A technically successful downgrade proves migration reversibility for this early schema; it is not a general production rollback guarantee once real data exists.

---

## 12. `SQLAlchemyUserRepository`

### 12.1 Construction

The adapter receives an existing `AsyncSession`:

```python
class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
```

It neither creates nor closes the session.

### 12.2 `add()`

```text
User
 ↓
user_to_model()
 ↓
UserModel
 ↓
session.add()
 ↓
await session.flush()
```

Allowed: mapping, `session.add`, `flush`, persistence-error translation.

Forbidden: merge, update, upsert, commit, rollback, refresh, begin, close, UUID generation, role assignment, email canonicalization.

### 12.3 `get_by_id()`

Use primary-key lookup semantics. Missing model → `None`; present model → `user_to_domain()`.

Application/Domain never receive `UserModel`.

### 12.4 `get_by_email()`

Use exact equality on canonical stored email. Infrastructure performs no `LOWER`, trim, or application normalization. Noncanonical lookup may return `None`; it must not be repaired silently.

---

## 13. Transaction ownership

The repository owns database operations, not the transaction boundary.

```text
SELECT      yes
session.add yes
flush       yes
mapping     yes
translation yes

begin       no
commit      no
rollback    no
close       no
```

The outer `AsyncSession` owner controls transaction lifecycle.

No productive `CreateUserUseCase`, Unit of Work, or provisioning service is introduced merely to manufacture a transaction owner. Integration tests may use a controlled external transaction owner.

---

## 14. Persistence-error translation

### 14.1 Identity conflicts

Both known identity uniqueness violations map to the same semantic exception:

```text
uq_users_email ─┐
                ├→ UserAlreadyExistsError
pk_users ───────┘
```

Translation uses structured PostgreSQL/asyncpg information in the SQLAlchemy exception chain: SQLSTATE/unique violation identity plus constraint identity.

The exact driver attribute path is implementation detail and must be confirmed against real PostgreSQL evidence.

### 14.2 Prohibited classification

Never classify by free-text parsing such as:

```python
"duplicate key" in str(exc)
```

or constraint-name substring search in the human-readable message.

### 14.3 Other persistence failures

Non-identity persistence failures crossing the adapter boundary use `UserRepositoryError`. Unknown failures are never falsely classified as duplicate identity.

### 14.4 Causality

Translated errors preserve diagnostic causes with `raise ... from exc`. SQLAlchemy/asyncpg/PostgreSQL exception classes do not become the Domain/Application public contract.

### 14.5 Failed flush

The repository does not call `rollback()` after failed `flush()`. The external transaction owner performs rollback.

---

## 15. Security-contract relationship

`NF-AUTH-02` implements only the identity-persistence subset of the frozen security design and preserves:

- UUID identity;
- canonical unique email;
- `ANALYST` / `ADMIN` roles;
- deny-by-default semantics;
- explicit role assignment;
- PostgreSQL primary persistence;
- SQLAlchemy/AsyncSession only in Infrastructure;
- Alembic-only migrations.

### `SEC-Q02`

Provisioning remains open:

- `User.create()` is not provisioning;
- the `users` table does not implement provisioning policy;
- no default role;
- no signup;
- no seed/admin/invitation mechanism selected here;
- closing `NF-AUTH-02` does not mark provisioning-dependent security ACs as `VERIFIED`.

`SEC-Q02` must be resolved before the future account-provisioning package and before complete closure of `NF-SEC-03`.

---

## 16. Verification strategy

Verification is layered.

### 16.1 Pure Domain tests

Verify:

- only ANALYST/ADMIN roles;
- unknown role failure;
- UUID generation in `User.create()`;
- outer strip + lowercase;
- immutability;
- valid and invalid email matrices;
- strict rehydration rejecting noncanonical persisted email.

Invalid categories include local hostname, multiple `@`, leading/trailing/consecutive local dots, invalid domain labels, Unicode, quoted local part, domain literal, local >64, total >254, whitespace/control characters.

### 16.2 Mapper unit tests

Verify both directions, round-trip ID/email/role, both roles, fail-closed invalid persisted role/email, and zero DB I/O/canonicalization/UUID generation/transaction handling.

### 16.3 ORM structural tests

Verify exact metadata for `users`, column types/nullability/defaults, and named constraints `pk_users`, `uq_users_email`, `ck_users_email_canonical`, `ck_users_role`.

Structural tests do not replace real PostgreSQL.

### 16.4 Real PostgreSQL migration tests

Verify auth revision descends from `116464527395`, one Alembic head, upgrade, physical schema, downgrade, re-upgrade, approved tables only, exact types/constraints/names/no server defaults.

### 16.5 Real PostgreSQL constraint tests

Direct DB tests prove uppercase/noncanonical email rejection, outer ordinary-space rejection, invalid-role rejection, and duplicate canonical-email rejection. Full email syntax remains Domain responsibility.

### 16.6 Real PostgreSQL repository tests

Must prove:

- `add()` + external commit persists;
- new session `get_by_id()` returns same Domain user;
- `get_by_email()` returns same Domain user;
- missing lookup returns `None`;
- noncanonical lookup is not normalized;
- `uq_users_email` → `UserAlreadyExistsError`;
- `pk_users` → `UserAlreadyExistsError`;
- raw `IntegrityError` does not leak;
- cause is preserved.

### 16.7 Flush/no-commit evidence

```text
Session A
  BEGIN
  repository.add(user)
  FLUSH
  NO COMMIT

Session B
  user not visible

Session A
  ROLLBACK

Session C
  user absent
```

This proves actual INSERT, repository flush, no repository commit, and external transaction ownership.

### 16.8 Mocks and SQLite

Mocks may verify collaboration only. SQLite/mocks cannot declare PostgreSQL UUID, named constraints, asyncpg metadata, transaction visibility, Alembic PostgreSQL DDL, or structured constraint translation verified.

### 16.9 Regression and quality

Without PostgreSQL: ordinary suite passes and integration tests may be controlled skips.

With PostgreSQL: migration, repository integration, and full regression pass.

Known baseline Ruff/mypy debt may remain documented; new debt attributable to `NF-AUTH-02` must be zero.

---

## 17. Implementation microiterations

Implementation is decomposed into six sequential packages. Approval of one package never authorizes the next.

### NF-AUTH-02-A — Domain Identity

Scope: `UserRole`, `User`, `InvalidUserEmailError`, canonicalization/validation, async `UserRepository`, repository semantic exceptions, pure Domain tests.

Forbidden: SQLAlchemy, ORM, Alembic, PostgreSQL, `AsyncSession`, repository adapter, provisioning/password/auth.

Gate:

```text
Domain unit tests       PASS
Domain framework deps   0
DB modifications        0
scope creep             0
```

**STOP.**

### NF-AUTH-02-B — ORM Model + Explicit Mapping

Scope: Infrastructure `Base`, `UserModel`, explicit mapper, structural metadata tests, mapper unit tests.

No Alembic revision, DB I/O, or repository adapter.

Gate:

```text
ORM metadata       PASS
Mapper tests       PASS
Domain unchanged   PASS
SQL executed       0
```

**STOP.**

### NF-AUTH-02-C — Users Alembic Migration

Scope: connect Alembic to `Base.metadata`, explicit model registration, autogenerate draft, mandatory review, migration only for `users`, real PostgreSQL round-trip and physical schema checks.

Gate:

```text
Alembic unique head           PASS
upgrade                       PASS
schema exact                  PASS
constraints exact             PASS
server defaults absent        PASS
downgrade                     PASS
re-upgrade                    PASS
unapproved business tables    0
```

**STOP.**

### NF-AUTH-02-D — Repository Adapter

Scope: `SQLAlchemyUserRepository`, exactly three methods, mapper reuse, structured-error translation code, isolated collaboration tests.

No productive transaction owner or Application wiring.

Gate:

```text
port implemented exactly       PASS
3 methods only                 PASS
mapping reused                 PASS
commit/rollback/lifecycle      0
SQLAlchemy leakage inward      0
Application wiring             0
```

**STOP.**

### NF-AUTH-02-E — Real PostgreSQL Behavioral Verification

Evidence-only package proving persistence/query behavior, constraints, identity-conflict translation, no raw SQLAlchemy leakage, external transaction ownership, rollback, and no repository canonicalization.

Gate:

```text
PostgreSQL real              PASS
Repository persistence       PASS
Repository queries           PASS
uq_users_email translation   PASS
pk_users translation         PASS
transaction ownership        PASS
external rollback            PASS
constraint defense           PASS
SQLite substitution          0
```

**STOP.**

### NF-AUTH-02-F — Independent QA / Final Gate

No new feature code. Audit installation/reproducibility, ordinary/integration tests, Alembic graph and round-trip, physical schema, layer boundaries, Ruff/mypy delta, dependency health, scope, secrets, and source mutation.

Negative scope audit:

```text
password_hash              0
Argon2                     0
login                      0
JWT                        0
refresh                    0
signup                     0
provisioning               0
account status             0
role mutation              0
forecast ownership         0
frontend                   0
Unit of Work               0
```

Allowed outcomes: `GO`, `GO WITH NON-BLOCKING BASELINE OBSERVATIONS`, or `NO-GO — CORRECTION REQUIRED`.

Only after this Gate may the package be declared `NF-AUTH-02 — IDENTITY PERSISTENCE CLOSED`.

---

## 18. Git and change-control discipline

Each microiteration follows:

```text
implement one microiteration
        ↓
required tests/evidence
        ↓
STOP
        ↓
architectural review
        ↓
controlled staging
        ↓
commit
        ↓
remote synchronization
        ↓
new baseline
        ↓
next microiteration only after authorization
```

Do not accumulate A+B+C before the first Gate. Do not silently alter this specification. Legitimate changes require explicit architectural change control.

---

## 19. Final implementation acceptance matrix

```text
Domain invariants                    PASS
Email profile                        PASS
Mapper round-trip                    PASS
ORM metadata                         PASS
Alembic unique head                  PASS
upgrade                              PASS
downgrade                            PASS
re-upgrade                           PASS
users physical schema                PASS
named constraints                    PASS
invalid role rejection               PASS
noncanonical email rejection         PASS
duplicate email rejection            PASS
repository add                       PASS
get_by_id                            PASS
get_by_email                         PASS
missing lookup                       PASS
uq_users_email translation           PASS
pk_users translation                 PASS
unexpected failure not misclassified PASS
external rollback                    PASS
repository commit                    0
raw SQLAlchemy leakage               0
SQLAlchemy dependency in Domain      0
SQLAlchemy dependency in Application 0
scope creep                          0
full regression                      PASS
new Ruff/mypy debt                   0
```

Green mocks cannot mark PostgreSQL, AsyncSession, Alembic, or asyncpg semantics verified.

---

## 20. Open decisions intentionally preserved

Outside this design:

- `SEC-Q01` — browser/API topology, cookies, CORS, CSRF;
- `SEC-Q02` — provisioning mechanism;
- `SEC-Q03` — `.pkl` custody;
- `SEC-Q04` — forecast sensitivity/classification;
- JWT claims;
- refresh replay/concurrency policy;
- role/account-transition policy;
- exceptional ADMIN forecast access;
- audit-event catalog;
- rate/size/time limits.

Only `SEC-Q02` is directly adjacent to this package and remains open because identity persistence is not account provisioning.

---

## 21. Final architectural resolution

The integral `D01–D19` review produced:

```text
NF-AUTH-02 — INTEGRAL DESIGN REVIEW D01–D19
DESIGN APPROVED WITH NON-BLOCKING OBSERVATIONS
```

The review observations incorporated here are:

1. `NF-AUTH-02` does not close `NF-SEC-03` or resolve `SEC-Q02`.
2. D08 supersedes D07's illustrative `save()` wording.
3. D11-A supersedes earlier `pk_users → UserRepositoryError` wording.
4. Constructor/rehydration invariants and the narrower meaning of `ck_users_email_canonical` are explicit.

No `D20` is required.

This file is the authoritative design input for the future implementation plan.

**Implementation remains NOT AUTHORIZED until this written specification is reviewed and explicitly approved.**

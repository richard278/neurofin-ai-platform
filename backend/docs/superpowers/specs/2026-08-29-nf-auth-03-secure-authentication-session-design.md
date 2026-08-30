# NF-AUTH-03 — Secure Authentication & Session
## Written Design Specification

**Project:** NeuroFin AI Platform
**Document date:** 2026-08-29
**Status:** APPROVED AS OFFICIAL
**Nature:** Architectural specification / contract
**Repository:** `richard278/neurofin-ai-platform`
**Branch:** `main`
**Input repository baseline:** `090de6c61c6f8d731df0ab24f13b73e788b28a3c`
**Security contractual baseline:** `24e418edb84c94d816a40b3b8f05ef1c20ef87cb`
**Predecessor:** `NF-AUTH-02 — Identity Persistence` — CLOSED
**Implementation authorization:** NOT AUTHORIZED
**Implementation Plan:** MATERIALIZED / SELF-REVIEW PASS

---

## 1. Purpose

This document materializes the approved architectural design of:

> **`NF-AUTH-03 — Secure Authentication & Session`**

Its purpose is to define the authoritative **WHAT** and **WHY** for secure authentication, short-lived access JWTs, stateful refresh sessions, refresh-token rotation, replay/reuse response, logout, browser transport, transaction boundaries, evidence requirements, and implementation decomposition.

This document does **not** authorize source-code changes, dependency installation, schema migrations, endpoint creation, cryptographic key generation, or PostgreSQL execution.

The implementation shall be planned only after this Written Design Specification passes the User Review Gate.

---

## 2. Contractual authority and precedence

### 2.1 Approved decision set

This specification consolidates the approved decisions:

- `NF-AUTH-03-D01` — Hybrid Session Model.
- `NF-AUTH-03-D02` — historical JWT Claims Contract approval.
- `NF-AUTH-03-D03` — Separate Credential Persistence.
- `NF-AUTH-03-D04` — Argon2id Password Contract.
- `NF-AUTH-03-D05` — Authentication Failure & Login Semantics.
- `NF-AUTH-03-D06` — Credential Repository & Transaction Ownership.
- `NF-AUTH-03-D07` — Refresh Session Persistence Model.
- `NF-AUTH-03-D08` — Atomic Refresh Rotation & Concurrent Reuse Semantics.
- `NF-AUTH-03-D09` — Refresh Token Cryptographic Contract.
- `NF-AUTH-03-D10` — Logout & Revocation Semantics.
- `NF-AUTH-03-D11` — Browser Transport / Cookie / CSRF Contract.
- `NF-AUTH-03-D12` — Verification Strategy & Security Gate.
- `NF-AUTH-03-D13` — Implementation Microiteration Decomposition.

It also incorporates the approved controlled reconciliations:

- `NF-AUTH-03-D01-A` — Session Lifetime & Clock Contract.
- `NF-AUTH-03-D06-A` — Rehash Transaction & Failure Semantics.
- `NF-AUTH-03-D02-R1` — JWT Claims Contract · Controlled Re-Ratification.

The Integral Design Review and its Controlled Re-Run are closed.

### 2.2 Precedence rules

Where earlier wording differs from a later approved refinement, the later approved refinement is authoritative.

The explicit precedence is:

1. **D01-A** is authoritative for access-token lifetime, refresh-generation lifetime, absolute refresh-session lifetime, clock semantics, and validation leeway.
2. **D06-A** is authoritative for opportunistic Argon2id rehash, transaction ordering, failure semantics, and compare-and-replace.
3. **D02-R1** is the authoritative JWT contract and supersedes the documentary gap left by the unavailable literal wording of historical D02.
4. D01–D13 remain authoritative for all areas not superseded by an approved refinement.

### 2.3 Documentary integrity of D02

The original D02 approval is historically established, but its exact original wording was not recovered.

This document shall **not** pretend otherwise.

`NF-AUTH-03-D02-R1` is a new explicit authoritative wording adopted through controlled re-ratification. It closes the documentary gap without rewriting history.

---

## 3. Architectural objective

NeuroFin requires authentication that demonstrates more than a working login form.

The target architecture must provide:

- cryptographically protected stored credentials;
- externally non-enumerating login failure behavior;
- short-lived, signed, stateless access tokens;
- stateful refresh sessions persisted in PostgreSQL;
- opaque, high-entropy refresh secrets;
- hash-only refresh persistence;
- single-use refresh generations;
- atomic rotation;
- deterministic reuse/replay response;
- family-level revocation;
- idempotent logout;
- explicit server-side time authority;
- browser transport that avoids persistent JavaScript-accessible tokens;
- strict Origin and CSRF defenses for browser authentication operations;
- restrictive CORS only where cross-origin development requires it;
- real PostgreSQL verification for properties dependent on transactions, locking, constraints, and migrations;
- independent final QA.

---

## 4. Scope

### 4.1 In scope

`NF-AUTH-03` owns:

- password credential persistence;
- Argon2id hashing and verification;
- credential lookup;
- opportunistic password-hash rehash;
- authentication of an existing identity;
- access JWT issuance and validation;
- refresh-session persistence;
- refresh-token generation and digesting;
- initial session issuance after valid authentication;
- refresh rotation;
- consumed-token reuse detection;
- family revocation;
- logout of the current refresh family;
- browser cookie transport for refresh;
- Origin validation;
- custom CSRF header enforcement;
- auth-specific CORS hardening;
- verification and evidence for these controls.

### 4.2 Explicitly out of scope

The following are not introduced by this phase:

- public signup;
- public registration;
- ADMIN provisioning API;
- invite flow;
- demo-account provisioning;
- password reset;
- password recovery;
- password-change endpoint;
- MFA;
- OAuth;
- OIDC;
- SSO;
- account lockout;
- CAPTCHA;
- rate limiting;
- global logout / logout-all;
- account-status lifecycle;
- `ACTIVE`, `LOCKED`, `DISABLED`, or equivalent invented states;
- functional authorization rules for business resources;
- forecast ownership;
- ADMIN exceptional access;
- audit-event catalogue;
- forecast sensitivity policy;
- ML artifact custody;
- access-token denylist;
- JWKS endpoint;
- dynamic signing-key discovery;
- cross-site production frontend architecture;
- device fingerprinting;
- IP/geo binding;
- `/auth/me` as an automatic addition.

`SEC-Q02 — provisioning` remains open and outside this phase.

---

## 5. Existing architectural baseline

`NF-AUTH-03` builds on `NF-AUTH-02`, which already provides the persistent identity model:

```text
Domain.User
├── id: UUID
├── email: canonical str
└── role: UserRole
    ├── ANALYST
    └── ADMIN
```

`Domain.User` remains unchanged by this design.

Authentication data is deliberately separated from identity data.

The existing repository baseline already has:

- Clean Architecture layer separation;
- PostgreSQL-backed identity persistence;
- SQLAlchemy 2.x async infrastructure;
- `AsyncSession`;
- Alembic;
- a pure Domain `User`;
- `UserRepository`;
- strict canonical email semantics;
- `ANALYST` / `ADMIN` role semantics;
- fail-closed role rehydration.

---

## 6. Clean Architecture boundaries

The intended dependency direction is:

```text
Presentation
    │
    ▼
Application / Security contracts
    │
    ├── UserRepository
    ├── CredentialRepository
    ├── PasswordHasher
    ├── AccessTokenService
    ├── RefreshTokenService
    └── Clock
    │
    ▼
Infrastructure adapters
    │
    ├── SQLAlchemy repositories
    ├── Argon2id adapter
    ├── JWT PS256 adapter
    ├── CSPRNG / Base64URL / SHA-256 adapter
    └── PostgreSQL
```

### 6.1 Domain restrictions

Domain shall not import:

- FastAPI;
- SQLAlchemy;
- `AsyncSession`;
- asyncpg;
- PostgreSQL libraries;
- JWT libraries;
- Argon2 libraries;
- cookie or CORS semantics.

### 6.2 Application restrictions

Application shall not import:

- FastAPI;
- SQLAlchemy;
- `AsyncSession`;
- cookie APIs;
- CORS middleware;
- HTTP exception classes.

Application may depend on language-level async contracts and security ports.

### 6.3 Infrastructure responsibility

Infrastructure owns:

- Argon2id implementation details;
- JWT signing and verification adapter;
- SQLAlchemy mappings;
- PostgreSQL repositories;
- CSPRNG/Base64URL/SHA-256 implementation;
- structured database-error translation;
- database-specific locking operations.

### 6.4 Presentation responsibility

Presentation owns:

- HTTP request/response translation;
- `401` response translation;
- auth endpoint routing;
- `Set-Cookie`;
- cookie clearing;
- Origin enforcement;
- CSRF header enforcement;
- CORS configuration;
- Bearer token extraction.

---

## 7. Core security invariants

The following are non-negotiable invariants.

### 7.1 Password secrecy

```text
plaintext password in PostgreSQL        = 0
plaintext password in logs              = 0
plaintext password in JWT               = 0
plaintext password in refresh state     = 0
```

Python cannot guarantee deterministic memory zeroization; this design does not claim it.

The requirement is to minimize logical lifetime and prohibit persistence or observation through logging, metrics, traces, exceptions, and audit payloads.

### 7.2 Refresh secrecy

```text
raw refresh in PostgreSQL                = 0
raw refresh in logs                      = 0
raw refresh in audit events              = 0
raw refresh in metrics/traces            = 0
raw refresh in JSON response             = 0
```

The raw refresh necessarily exists transiently during issuance/rotation and is delivered through the `Set-Cookie` response header. That required transient handling is not classified as leakage.

### 7.3 Browser token storage

```text
access JWT in localStorage               = 0
access JWT in sessionStorage             = 0
access JWT in IndexedDB                  = 0
access JWT in persistent cookie          = 0

refresh readable by JavaScript           = 0
```

The access JWT lives only in frontend runtime memory.

The refresh secret is browser-managed through an HttpOnly cookie.

### 7.4 Server authority

The client never decides:

- role;
- permissions;
- token validity;
- token expiration;
- session revocation;
- refresh reuse;
- clock time.

---

## 8. Hybrid session model

NeuroFin uses two security artifacts with deliberately different semantics.

### 8.1 Access token

The access token is:

- a signed JWT;
- stateless per token;
- short-lived;
- validated without a per-request access-token database lookup;
- transported as `Authorization: Bearer <token>`;
- stored in frontend runtime memory only.

There is no access-token persistence table and no access-token denylist in this phase.

### 8.2 Refresh session

The refresh side is:

- stateful;
- server-revocable;
- persisted in PostgreSQL;
- composed of a refresh family/session plus token generations;
- single-use per generation;
- replay/reuse detectable;
- capable of server-side logout.

### 8.3 Consequence of the hybrid model

Logout immediately prevents further refresh within the revoked family.

An already-issued access JWT may remain valid until its normal temporal validation fails.

This is intentional and shall not be “fixed” by silently introducing an access-token denylist.

---

## 9. Session lifetime and Clock contract

D01-A defines the authoritative temporal policy.

### 9.1 Access JWT

```text
nominal TTL = 10 minutes
validation leeway <= 30 seconds
```

The JWT is emitted with a nominal expiration of ten minutes.

The leeway exists only during temporal validation.

Therefore:

```text
exp = issuance_reference + 10 minutes
```

not:

```text
exp = issuance_reference + 10 minutes + 30 seconds
```

### 9.2 Refresh generation

Each refresh generation has a maximum nominal lifetime of:

```text
30 minutes
```

Refresh has:

```text
grace period = 0
clock leeway = 0
```

Its expiration is:

```text
refresh_token.expires_at
=
min(
    refresh_token.issued_at + 30 minutes,
    refresh_session.absolute_expires_at
)
```

### 9.3 Absolute refresh session

Each newly authenticated refresh session has:

```text
absolute lifetime = 8 hours
```

The absolute expiration is non-sliding.

Rotation never extends it.

Once `now >= absolute_expires_at`:

- no successor refresh token is issued;
- no new access JWT is issued from that family;
- fresh credential authentication is required.

### 9.4 Clock

Security time is obtained from a server-side, timezone-aware UTC `Clock` abstraction.

Conceptually:

```python
class Clock(Protocol):
    def now(self) -> datetime:
        ...
```

The returned value must be UTC and timezone-aware.

The browser clock has no authority over security decisions.

Security timestamps persisted in PostgreSQL use timezone-aware semantics compatible with `TIMESTAMPTZ`.

### 9.5 Refresh under locking

For refresh state-machine decisions, the authoritative `now` is sampled or re-sampled after the required locks are obtained.

A request that started before expiration but waited on a lock until expiration is evaluated against the current authoritative time under lock.

### 9.6 No artificial keepalive

The frontend shall not perform background refresh whose sole purpose is to keep an otherwise idle session alive.

This phase does not introduce a separate user-activity tracker.

---

## 10. JWT contract

D02-R1 is the authoritative access-token contract.

### 10.1 Signing algorithm

The only allowed algorithm is:

```text
PS256
```

The validator uses a fixed server-side allowlist:

```text
allowed algorithms = {PS256}
```

The algorithm declared by the token is never trusted to select verification behavior.

There is no fallback to:

- `none`;
- HS256;
- RS256;
- another algorithm.

A future algorithm migration requires Change Control.

### 10.2 Key ownership

Private signing key:

- server-side only;
- used for signing;
- never committed to Git;
- never exposed to frontend code.

Public verification key:

- trusted server-side configuration;
- used for validation.

This baseline does not introduce:

- JWKS endpoint;
- dynamic `jku`;
- `x5u`;
- client-supplied key URLs;
- automatic remote key retrieval;
- multi-key rotation protocol;
- `kid` as a required baseline field.

### 10.3 JWT header

The contractual header is:

```text
alg = PS256
typ = neurofin-access+jwt
```

The `typ` value distinguishes NeuroFin access JWTs from possible future JWT uses.

### 10.4 Mandatory claims

The required contractual claims are exactly:

```text
sub
iss
aud
iat
exp
jti
role
```

### 10.5 Claim semantics

| Claim | Contract |
|---|---|
| `sub` | canonical string representation of the authenticated `User.id` UUID |
| `iss` | exactly `urn:neurofin:auth` |
| `aud` | exactly `urn:neurofin:api` |
| `iat` | UTC NumericDate governed by server Clock |
| `exp` | UTC NumericDate, nominally `iat + 10 minutes` |
| `jti` | new UUIDv4 for each access JWT |
| `role` | exactly `ANALYST` or `ADMIN` |

`jti` is not persisted and is not used as a denylist key.

### 10.6 Role snapshot semantics

`role` is loaded from authoritative server-side identity state at issuance.

For every new access JWT created through login or refresh:

```text
load current User
    ↓
read authoritative User.role
    ↓
issue new access JWT
```

An already-issued access JWT is a stateless snapshot.

If the user role changes after issuance, the old token may retain its old role until it expires.

This short residual window is an accepted trade-off of the stateless access model.

### 10.7 Account status

There is no authoritative `account_status` model in the current identity design.

Therefore this phase does not invent:

```text
ACTIVE
DISABLED
LOCKED
SUSPENDED
```

and does not emit an `account_status` claim.

Adding such a model requires Change Control defining its effect on login, refresh, and already-issued access tokens.

### 10.8 Excluded access-token data

The access JWT shall not contain:

- email;
- plaintext password;
- password hash;
- refresh secret;
- refresh digest;
- internal refresh-session identifier;
- IP address;
- user agent;
- geolocation;
- device fingerprint;
- forecast IDs.

### 10.9 Validation pipeline

Conceptually:

```text
receive JWT
   ↓
syntactic parse
   ↓
typ == neurofin-access+jwt
   ↓
alg == PS256
   ↓
verify signature with trusted public key
   ↓
require sub, iss, aud, iat, exp, jti, role
   ↓
iss exact
   ↓
aud exact
   ↓
iat / exp temporal validation
   ↓
sub canonical UUID
   ↓
jti canonical UUID
   ↓
role ∈ {ANALYST, ADMIN}
   ↓
authenticated principal
```

Any failure produces no partial principal and no fallback role.

Additional unknown claims have no authentication or authorization meaning.

---

## 11. Credential persistence model

Credentials are separated 1:1 from identity.

Conceptually:

```text
users
├── id
├── email
└── role
     │
     │ 1 : 1
     ▼
user_credentials
├── user_id      PK / FK → users.id
└── password_hash TEXT NOT NULL
```

### 11.1 Identity remains pure

`Domain.User` does not gain `password_hash`.

`user_credentials` does not duplicate:

- email;
- role.

### 11.2 Stored representation

The stored password representation is an opaque PHC string.

The database does not store a separate salt column.

The database does not impose a rigid `CHECK` requiring a `$argon2id$` prefix.

Cryptographic interpretation belongs to `PasswordHasher`, not PostgreSQL schema logic.

### 11.3 Referential behavior

This specification does not invent an unapproved `ON DELETE CASCADE` policy.

Delete semantics for identity/credentials remain outside this phase unless a later controlled decision defines them.

---

## 12. PasswordHasher and Argon2id

Application depends on:

```python
class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        ...

    def verify(self, password: str, encoded_hash: str) -> bool:
        ...

    def needs_rehash(self, encoded_hash: str) -> bool:
        ...
```

### 12.1 Cryptographic policy

New credentials use:

```text
Argon2id
```

The salt is generated by the Argon2 implementation.

Application never provides or persists the salt separately.

### 12.2 Parameter selection

Argon2 memory cost, time cost, and parallelism are:

- explicit;
- configuration-backed;
- measured;
- justified by benchmark evidence.

This design deliberately does not freeze tutorial-derived numeric constants.

`03-A` must benchmark the selected baseline and record:

- execution environment;
- memory cost;
- time cost;
- parallelism;
- measured latency;
- justification.

### 12.3 Malformed or unsupported hashes

Malformed or unsupported encoded hashes fail closed.

They may produce sanitized internal diagnostics but never expose PHC content or implementation detail through the authentication response.

### 12.4 Pepper

No password pepper is part of the current baseline.

Introducing one requires its own lifecycle, rotation, deployment, and recovery design.

---

## 13. Authentication semantics

The conceptual input is:

```python
AuthenticateCommand(
    email: str,
    password: str,
)
```

The password is transient input.

### 13.1 Email handling

Authentication reuses the existing identity canonicalization rule.

The repository receives the canonical email.

Neither SQL nor Infrastructure duplicates identity logic through:

```text
LOWER(email)
strip().lower()
```

as an authentication rule.

### 13.2 Valid credentials

Success requires all of:

```text
User found
Credential found
PasswordHasher.verify(password, password_hash) == True
```

Only then is the user authenticated.

### 13.3 Externally indistinguishable failure

These internal causes produce the same external authentication failure:

```text
unknown email
wrong password
missing credential
```

The Presentation-layer contract is a generic:

```text
401 Unauthorized
```

No response discloses whether the identity exists.

### 13.4 Dummy Argon2 verification

For an unknown identity, the authentication flow executes an Argon2id verification against a controlled dummy PHC compatible with the active policy.

The dummy hash is:

- controlled configuration;
- non-secret;
- not generated expensively on every request;
- not a user credential.

The goal is to remove a trivial branch where unknown users perform no password-hash work.

The design does not claim constant-time login.

### 13.5 Missing credentials

A known `User` with no credential still fails externally as generic `401`.

Internally it is an integrity/security condition and may be diagnosed without exposing details.

### 13.6 FastAPI separation

Application emits semantic success/failure.

It does not construct a FastAPI `HTTPException`.

Presentation translates authentication failure to HTTP.

---

## 14. CredentialRepository

Application/Security uses an immutable credential object:

```python
@dataclass(frozen=True)
class PasswordCredential:
    user_id: UUID
    password_hash: str
```

`password_hash` is opaque to Application.

### 14.1 Port

The authoritative refined port is conceptually:

```python
class CredentialRepository(Protocol):
    async def add(
        self,
        credential: PasswordCredential,
    ) -> None:
        ...

    async def get_by_user_id(
        self,
        user_id: UUID,
    ) -> PasswordCredential | None:
        ...

    async def replace_hash(
        self,
        user_id: UUID,
        expected_hash: str,
        replacement_hash: str,
    ) -> bool:
        ...
```

### 14.2 `add()`

`add()` is insert-only.

It is not:

- merge;
- upsert;
- update;
- silent replacement.

A second credential for the same user is a semantic conflict.

### 14.3 Error taxonomy

Repository errors are semantic Application-facing errors.

Conceptually:

```text
CredentialRepositoryError
└── CredentialAlreadyExistsError
```

A duplicate credential constraint maps to `CredentialAlreadyExistsError`.

The adapter uses structured PostgreSQL/driver metadata, including SQLSTATE/constraint metadata when relevant.

Human-readable exception-message parsing is prohibited.

Technical causality is preserved.

### 14.4 Transaction ownership

The SQLAlchemy adapter receives an existing `AsyncSession`.

It may:

- execute queries;
- add/update ORM state;
- `flush()`.

It may not own:

- `commit()`;
- `rollback()`;
- `close()`;
- the session lifecycle.

---

## 15. Opportunistic rehash and compare-and-replace

D06-A refines rehash behavior.

### 15.1 Authentication validity is independent

Once:

```text
verify(password, stored_hash) == True
```

the credential is valid for that authentication attempt.

A stale hash policy does not make the credential invalid.

### 15.2 Rehash candidate

If:

```text
needs_rehash(stored_hash) == True
```

the current plaintext password, already validated for the login operation, may be used once to generate a new PHC under the current Argon2id policy.

The plaintext is not propagated in an authentication-result object.

### 15.3 Transaction ordering

The ordering is:

```text
verify credential
      ↓
determine optional rehash
      ↓
prepare replacement PHC if needed
      ↓
BEGIN core session transaction
      ↓
persist refresh session + R1 digest
      ↓
COMMIT
      ↓
core login durable
      ↓
optional separate rehash transaction
```

The rehash write never precedes successful durable session creation.

### 15.4 Rehash failure

If the maintenance transaction fails:

```text
maintenance rollback
old valid PHC remains
login remains successful
newly committed session is not revoked
```

There is one controlled persistence attempt.

No retry loop or background worker is introduced.

### 15.5 Compare-and-replace

The repository replaces only the exact PHC that was verified:

```text
UPDATE credential
WHERE user_id = ?
  AND password_hash = expected_hash
```

Conceptually:

```text
True
→ exact expected PHC was still current and replacement flushed

False
→ credential changed concurrently
→ no overwrite
→ maintenance no-op
```

This prevents a stale login request from overwriting a newer credential state.

`replace_hash()` is not a password-change, reset, recovery, or provisioning API.

---

## 16. Refresh persistence model

Refresh state is separated into a session/family and retained token generations.

### 16.1 `refresh_sessions`

Conceptual fields:

```text
refresh_sessions
├── id
├── user_id
├── created_at
├── absolute_expires_at
└── revoked_at
```

Properties:

- one user may have multiple refresh sessions;
- `revoked_at` is authoritative family revocation state;
- `absolute_expires_at` is non-sliding;
- timestamps are timezone-aware.

### 16.2 `refresh_tokens`

Conceptual fields:

```text
refresh_tokens
├── id
├── session_id
├── parent_token_id
├── token_hash
├── issued_at
├── expires_at
└── consumed_at
```

Properties:

- generations are retained after consumption;
- raw token is never persisted;
- successor relationship is explicit;
- one parent has at most one successor.

### 16.3 Physical invariants

The schema must enforce at least:

```text
UNIQUE(token_hash)
UNIQUE(parent_token_id)
```

`token_hash` is stored as a 32-byte binary SHA-256 digest using a PostgreSQL binary type such as `BYTEA`.

Security timestamps use timezone-aware PostgreSQL semantics.

This specification does not invent database identifier types or cascade/delete rules that were not explicitly frozen.

### 16.4 Valid generation state

A presented refresh generation is valid only when:

```text
token found
AND token consumed_at IS NULL
AND now < token.expires_at
AND session.revoked_at IS NULL
AND now < session.absolute_expires_at
```

A consumed generation is not an expired-token shortcut.

When a consumed token is presented while its family is still active, it is classified as reuse and triggers family revocation.

---

## 17. Refresh token cryptographic contract

### 17.1 Secret generation

Every generation uses:

```text
32 independent CSPRNG bytes
= 256 bits
```

Each successor is cryptographically independent from its parent.

No token is derived from:

- timestamp;
- user ID;
- parent secret;
- incremental sequence;
- `random.Random`;
- a JWT.

### 17.2 External representation

The 32 bytes are encoded as canonical unpadded Base64URL.

Contract:

```text
length = 43 characters
alphabet = A-Z a-z 0-9 _ -
padding "=" = forbidden
"+" = forbidden
"/" = forbidden
whitespace = forbidden
```

Strict decoding must yield exactly 32 bytes.

Only one canonical textual representation is accepted.

### 17.3 Digest

Persistence lookup uses:

```text
SHA-256(decoded_32_bytes)
```

which produces:

```text
32-byte binary digest
```

Argon2id is not used for refresh secrets because refresh secrets have high machine-generated entropy rather than human-password entropy.

### 17.4 RefreshTokenService

Conceptually:

```python
class RefreshTokenService(Protocol):
    def issue(self) -> IssuedRefreshToken:
        ...

    def digest(self, raw_token: str) -> bytes:
        ...
```

Infrastructure owns CSPRNG, Base64URL, and SHA-256 details.

### 17.5 No HMAC / pepper

No server HMAC/pepper secret is introduced for refresh digesting in this baseline.

The refresh secret already has 256 bits of CSPRNG entropy.

Adding HMAC would introduce another secret lifecycle without a demonstrated baseline requirement.

### 17.6 Collision behavior

A digest uniqueness collision is a security/invariant anomaly.

The transaction rolls back.

The design does not require an unbounded “generate until unique” retry loop.

---

## 18. Initial login session issuance

After credentials are valid, login creates:

```text
access JWT
+
refresh_session S1
+
refresh generation R1
```

### 18.1 Core transaction

Conceptually:

```text
prepare access JWT data
prepare raw R1 + digest
      ↓
BEGIN
      ↓
create refresh_session
create refresh_token R1 digest
      ↓
flush
      ↓
COMMIT
```

Only after successful commit may the caller receive:

- the access JWT;
- the raw refresh secret through the transport mechanism.

If persistence fails:

```text
ROLLBACK
no usable raw refresh returned
no successful access/session response returned
```

The system never returns a refresh secret whose durable server state failed to commit.

### 18.2 Provisioning remains separate

Tests may prepare identities and credentials through controlled fixtures or repository-level setup.

That does not create or authorize:

- `/signup`;
- public registration;
- ADMIN provisioning endpoint.

---

## 19. Atomic refresh rotation

Refresh rotation is serialized by PostgreSQL.

### 19.1 Non-authoritative lookup

The raw token is:

```text
strict decode
    ↓
SHA-256 digest
    ↓
pre-read token lookup
    ↓
obtain session_id
```

The pre-read is only for locating the session.

It is not authorization to rotate.

### 19.2 Lock order

All refresh and logout operations use the same lock order:

```text
1. refresh_session
2. refresh_token generation
```

The implementation uses `SELECT ... FOR UPDATE`.

It does not use `SKIP LOCKED` or `NOWAIT` for the baseline refresh state machine.

A competing request waits and then observes committed current state.

### 19.3 Revalidation under lock

After locks are acquired, state is re-read and evaluated using authoritative current time.

The decision order is:

```text
1. session revoked?
   → reject

2. session absolute expired?
   → reject

3. token consumed?
   → REUSE
   → revoke active family
   → commit revocation
   → reject

4. token expired?
   → reject

5. otherwise
   → rotate
```

### 19.4 Atomic `R1 → R2`

A valid rotation performs in one transaction:

```text
R1.consumed_at = now

+

INSERT R2(
    same session,
    parent_token_id = R1.id,
    token_hash = digest(R2),
    issued_at = now,
    expires_at = bounded expiry
)
```

Then:

```text
flush
COMMIT
```

Only after commit is R2 delivered.

If R2 insertion fails:

```text
ROLLBACK
R1 remains unconsumed
R2 does not exist
```

### 19.5 Single successor

`UNIQUE(parent_token_id)` prevents:

```text
R1 → R2
R1 → R3
```

even if application logic regresses.

### 19.6 Concurrent same-R1 reuse

For two truly concurrent requests:

```text
Request A → R1
Request B → R1
```

the first may rotate and commit `R1 → R2`.

The second waits, locks, and sees `R1.consumed_at != NULL`.

It is classified as reuse.

The second request revokes the entire refresh session/family and commits the revocation before returning the rejection.

Therefore R2 may physically exist but is unusable after the family is revoked.

### 19.7 Strict replay semantics

There is:

```text
grace window = 0
idempotent retry of consumed refresh = NO
```

If a client loses the R2 response and retries R1, the retry is reuse and causes family revocation.

This strict behavior is an explicit accepted security/usability trade-off.

---

## 20. Logout and revocation

### 20.1 Current-family scope

Logout revokes only the refresh session/family identified by the presented session credential.

Other sessions for the same user remain active.

### 20.2 Server-side meaning

Logout is not merely cookie deletion.

For a known active family:

```text
BEGIN
lock session
lock token as required
set session.revoked_at = now
flush
COMMIT
```

Success is not reported before the revocation is durable.

### 20.3 Idempotent external semantics

Logout is externally idempotent.

Conceptually:

```text
active known family        → revoke → success
already revoked family     → success
known expired token        → revoke active family if needed → success
known consumed token       → reuse semantics / family revoke → success outward
unknown token              → no server mutation → generic success
missing token              → no server mutation → generic success
```

The intended HTTP status is:

```text
204 No Content
```

once transport-level security checks have passed and the server-side outcome is complete.

### 20.4 Refresh versus logout race

Refresh and logout share the same lock order.

Regardless of which request obtains the lock first, the required final invariant is:

```text
session.revoked_at != NULL
usable successor = 0
```

A successor may physically exist if refresh committed first, but family revocation makes it unusable.

> Logout wins semantically.

### 20.5 Access token after logout

Logout does not persist or denylist access JWTs.

An access JWT issued before logout may remain valid until its nominal expiration, subject to the bounded D01-A validation leeway.

This is intentional.

---

## 21. Browser transport

### 21.1 Production topology

The target production topology is same-origin:

```text
https://neurofin.example/
├── React application
└── /api/...
    └── FastAPI
```

A reverse proxy may route browser traffic to separate internal processes without changing the same-origin browser boundary.

### 21.2 Access JWT

The access JWT is returned in the response body and retained only in frontend runtime memory.

Ordinary protected API calls use:

```text
Authorization: Bearer <access JWT>
```

The refresh cookie is not an authentication mechanism for ordinary business API endpoints.

### 21.3 Refresh cookie

The refresh cookie contract is exactly:

```text
Name      = __Host-neurofin_refresh
HttpOnly  = true
Secure    = true
SameSite  = Strict
Path      = /
Domain    = absent
```

The `__Host-` prefix requires the host-only semantics above.

### 21.4 Cookie lifetime

Cookie lifetime is derived from the current refresh generation’s remaining lifetime.

It must satisfy:

```text
cookie lifetime
<= current refresh remaining lifetime
<= absolute refresh-session remaining lifetime
```

There is no independent fourth session-duration policy.

### 21.5 Rotation and cookie replacement

For refresh:

```text
rotate and commit R2
      ↓
only after commit
      ↓
Set-Cookie(raw R2)
```

A raw successor is not sent before its server-side state is durable.

### 21.6 Logout cookie clearing

After server-side logout semantics complete, Presentation clears the refresh cookie using `Max-Age=0` with attributes compatible with the original cookie.

Unknown/missing refresh may still produce cookie clearing after valid transport-level security checks.

---

## 22. Origin and CSRF contract

`login`, `refresh`, and `logout` are browser-sensitive authentication operations.

Defense in depth requires both Origin validation and a custom non-simple CSRF header.

### 22.1 Trusted Origin

For these endpoints, `Origin` is required.

The server compares the full configured trusted origin exactly.

Rejected values include:

- wrong origin;
- lookalike origin;
- `Origin: null`;
- missing Origin;
- substring/suffix tricks.

Example:

```text
trusted:
https://neurofin.example

rejected:
https://neurofin.example.attacker.com
```

No reflected Origin policy is permitted.

### 22.2 Custom header

Browser authentication requests require:

```text
X-NeuroFin-CSRF: 1
```

The value is not a secret.

Its role is to require a non-simple request controlled by the trusted application.

A missing or incorrect required header is rejected before authentication/session mutation.

### 22.3 SameSite does not replace CSRF checks

`SameSite=Strict` is one layer.

It does not remove the explicit Origin + custom-header contract.

### 22.4 Access token not required for refresh/logout

Refresh and logout authenticate the refresh session through the cookie and their transport defenses.

They do not require a still-valid access JWT.

---

## 23. CORS contract

### 23.1 Production

The intended production deployment is same-origin and should not require permissive cross-origin credentialed access.

### 23.2 Development

Development may use separate frontend/API origins.

When CORS is needed:

- trusted origins are explicit configuration;
- `allow_credentials=true`;
- wildcard origins are prohibited;
- allowed methods are minimized;
- allowed headers are minimized;
- auth transport includes `X-NeuroFin-CSRF`;
- ordinary API needs may include `Authorization`;
- JSON requests may require `Content-Type`.

### 23.3 Repository baseline integration note

The current repository baseline mounts the API router under the configured `Settings.api_prefix`, whose current default is:

```text
/api/v1
```

The current baseline CORS middleware already uses configured origins and `allow_credentials=True`, but still allows wildcard methods and headers.

That baseline state is **not** the final D11 security contract.

`03-H` must tighten methods/headers and add the explicit Origin/CSRF behavior rather than treating the current permissive method/header settings as sufficient.

Trusted development origin values remain configuration-driven; this design does not freeze a frontend dev port.

---

## 24. HTTP auth surface and routing

The logical endpoint suffixes are:

```text
/auth/login
/auth/refresh
/auth/logout
```

They live beneath the existing configured API prefix.

With the repository’s current default:

```text
Settings.api_prefix = "/api/v1"
```

the default external route shape becomes:

```text
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
```

The API prefix remains configuration-driven; this phase does not introduce a second independent API versioning scheme.

`/auth/me` is not part of `NF-AUTH-03` by default.

If a future phase needs it, its principal and authorization semantics must be designed explicitly rather than added as incidental scope.

---

## 25. Transaction boundaries

### 25.1 Credential authentication

Credential verification itself is read-oriented.

Authentication success is established before session creation.

### 25.2 Core login session transaction

```text
BEGIN
create refresh_session
create R1 digest
flush
COMMIT
```

Only after commit may the caller receive successful access/refresh artifacts.

### 25.3 Opportunistic rehash transaction

The rehash transaction is separate and occurs only after the core login session has committed.

A maintenance failure does not undo a valid committed login session.

### 25.4 Refresh rotation transaction

```text
BEGIN
lock session
lock token
revalidate
consume R1
insert R2
flush
COMMIT
```

The raw R2 leaves the service only after commit.

### 25.5 Reuse revocation transaction

Reuse detection requires durable revocation.

The family revocation must be committed before the request returns the outward rejection.

Application flow must not raise an exception inside a transaction-management construct if that exception would roll back the security response it is trying to preserve.

### 25.6 Logout transaction

Logout revocation must commit before success is reported.

### 25.7 Repository rule

Repositories do not own:

```text
commit
rollback
close
```

Transaction ownership remains with the application/session orchestration boundary.

---

## 26. Security state and external response semantics

| Internal condition | Server mutation | External result |
|---|---|---|
| valid credentials | create session + R1 | success |
| unknown email | none | generic `401` |
| wrong password | none | generic `401` |
| missing credential | none | generic `401` |
| malformed stored password hash | none | generic `401`; sanitized internal diagnostic |
| valid access JWT | none | principal accepted |
| invalid/tampered JWT | none | `401` |
| access JWT expired beyond leeway | none | `401` |
| malformed refresh | none | generic refresh failure |
| unknown refresh | none | generic refresh failure |
| active refresh | consume + successor | success |
| refresh token expired | none | `401`, no rotation |
| refresh family revoked | none | `401`, no rotation |
| consumed refresh in active family | revoke family | `401` |
| absolute session expired | none | `401`, fresh login required |
| logout active known family | revoke family | `204` |
| logout already revoked family | no additional required mutation | `204` |
| logout unknown/missing refresh | no server mutation | `204` after valid transport checks |

No error payload exposes raw tokens, PHC strings, constraint names, signing details, or account-existence information.

---

## 27. Secret and diagnostic handling

### 27.1 Never log

The following must not be logged:

- plaintext password;
- password PHC;
- raw refresh token;
- JWT signature material;
- private signing key;
- full access JWT as a diagnostic payload.

### 27.2 Internal classification

The refresh path may distinguish internal states such as:

```text
INVALID_FORMAT
UNKNOWN
EXPIRED
REVOKED
REUSE
```

because `REUSE` has a different server-side security response.

External error messages remain non-enumerating.

### 27.3 Signing secrets

No production signing private key may be hardcoded or committed.

The public key may be configured as trusted verification material, but no dynamic client-controlled key lookup is allowed.

---

## 28. Verification strategy

Security claims become evidence only through execution.

The verification layers are:

```text
PURE CONTRACT TESTS
        ↓
CRYPTOGRAPHIC ADAPTER TESTS
        ↓
ORM / SCHEMA STRUCTURAL TESTS
        ↓
REAL POSTGRESQL INTEGRATION
        ↓
REAL CONCURRENCY TESTS
        ↓
HTTP / SECURITY INTEGRATION
        ↓
BROWSER TRANSPORT CONTRACT
        ↓
FULL REGRESSION
        ↓
INDEPENDENT QA
```

### 28.1 Argon2 verification

Required evidence includes:

- correct password verifies;
- wrong password rejects;
- salts produce distinct PHC values;
- malformed/unsupported PHC fails closed;
- `needs_rehash` identifies policy drift;
- benchmark-selected parameters are explicit;
- plaintext persistence/logging is zero.

### 28.2 Login verification

Required evidence includes:

```text
unknown email
wrong password
missing credential
        ↓
same external 401 contract
```

Unknown email must execute dummy Argon2 verification.

The evidence shall not claim constant-time login.

### 28.3 JWT matrix

At minimum:

- valid token;
- expired token;
- tampered token;
- wrong issuer;
- wrong audience;
- invalid/non-canonical subject;
- unknown role;
- missing mandatory claim;
- forbidden algorithm;
- wrong `typ`;
- malformed JWT;
- temporal value outside permitted leeway.

### 28.4 Real PostgreSQL migration verification

Authentication/session tables must be verified through:

```text
Alembic upgrade
physical schema inspection
Alembic downgrade
Alembic re-upgrade
```

PostgreSQL-real semantics are mandatory for:

- PK/FK/UNIQUE behavior;
- transaction ownership;
- rollback;
- `SELECT ... FOR UPDATE`;
- concurrent refresh;
- family revocation;
- race behavior.

SQLite is not a substitute for those properties.

### 28.5 Refresh cryptography verification

Evidence must prove:

- 32-byte CSPRNG source;
- 43-character canonical unpadded Base64URL;
- strict alphabet;
- strict decoded length;
- SHA-256 32-byte digest;
- raw token absent from DB;
- distinct generations;
- malformed encodings rejected.

### 28.6 Concurrent same-R1 verification

The concurrency test must use two genuinely concurrent transactions.

Sequentially calling refresh twice is not sufficient evidence of locking behavior.

Required final properties:

```text
children(R1) <= 1
R1 consumed
second use classified as REUSE
family revoked
R2 unusable after family revocation
```

### 28.7 Rotation rollback verification

A forced successor-insert failure must prove:

```text
R1 remains unconsumed
R2 does not exist
```

### 28.8 Logout race verification

A real concurrent:

```text
refresh(R1)
vs
logout(R1)
```

must finish with:

```text
family revoked
usable successor = 0
```

### 28.9 Browser contract verification

Tests must verify exact `Set-Cookie` attributes:

```text
__Host-neurofin_refresh
HttpOnly
Secure
SameSite=Strict
Path=/
Domain absent
```

Origin cases:

- configured trusted origin allowed;
- wrong origin rejected;
- lookalike origin rejected;
- `Origin: null` rejected;
- missing Origin rejected where required.

CSRF cases:

- `X-NeuroFin-CSRF: 1` present;
- missing header rejected.

CORS cases:

- explicit known development origin;
- unknown origin denied;
- credentials explicit;
- wildcard + credentials prohibited.

### 28.10 Access token after logout

A specific test must prove that:

```text
access JWT issued
      ↓
logout
      ↓
refresh family revoked
      ↓
existing access JWT remains valid
until temporal validation fails
```

This is an intentional architecture property, not a defect.

---

## 29. Clean Architecture verification

Final QA must demonstrate at least:

```text
Domain imports FastAPI       = 0
Domain imports SQLAlchemy    = 0
Domain imports JWT library   = 0
Domain imports Argon2 library= 0

Application imports FastAPI  = 0
Application imports SQLAlchemy = 0
Application owns cookie semantics = 0
```

Concrete dependencies point inward through ports and are implemented by Infrastructure/Presentation adapters.

---

## 30. Secret leakage audit

The final Gate requires evidence for:

```text
plaintext password in DB                 = 0
plaintext password in logs               = 0
raw refresh in DB                        = 0
raw refresh in logs                      = 0
access JWT in persistent browser storage = 0
refresh in JSON response                 = 0
hardcoded production signing key         = 0
tracked production secret                = 0
```

Audits must distinguish variable/field names from actual secret values.

---

## 31. NF-SEC traceability

The governing security baseline already defines:

```text
Threat
   ↓
Security Requirement
   ↓
Acceptance Criterion
   ↓
Verification
   ↓
Evidence
   ↓
Gate
```

Evidence naming remains:

```text
EV-NF-SEC-<AC-ID>-<METHOD>-<NN>
```

This specification does not invent a parallel evidence taxonomy.

### 31.1 Exact AC crosswalk rule

The canonical `NF-SEC-00-E` matrix remains the authority for exact per-criterion identifiers.

This document intentionally does **not** fabricate numeric `AC-NF-SEC-*` mappings from memory.

During evidence planning and `03-I`, the exact criterion IDs must be read from the canonical matrix and linked to the applicable tests/evidence without renumbering or guessing.

This is a traceability rule, not an unresolved design decision.

### 31.2 Security Gate alignment

Conceptually:

- credential/password/login/JWT evidence aligns with `NF-SEC-04`;
- refresh rotation/reuse/revocation/logout evidence aligns with `NF-SEC-05`;
- browser cookie/CORS/CSRF evidence aligns with the browser-security Gate associated with D11;
- integrated and independent evidence must preserve the existing `NF-SEC-00` evidence chain.

---

## 32. Final Security Gate

`NF-AUTH-03` may close only when all security-critical controls required by D12 are satisfied.

Required categories include:

| Gate | Required result |
|---|---|
| Credential / Argon2 contract | PASS |
| Argon2 benchmark evidence | PASS |
| Login anti-enumeration | PASS |
| JWT positive/negative matrix | PASS |
| Credential PostgreSQL persistence | PASS on real PostgreSQL |
| Refresh migration round-trip | PASS on real PostgreSQL |
| Refresh crypto contract | PASS |
| Atomic `R1 → R2` | PASS on real PostgreSQL |
| Concurrent same-R1 reuse | PASS on real PostgreSQL |
| Family revocation | PASS |
| Refresh vs logout race | PASS on real PostgreSQL |
| Logout idempotency | PASS |
| Expired/revoked token rejection | PASS |
| Browser cookie contract | PASS |
| Origin/CSRF/CORS matrix | PASS |
| Secret leakage audit | PASS |
| Clean Architecture boundaries | PASS |
| Full regression with PostgreSQL | 0 FAIL |
| Independent QA | PASS |
| Source mutation during final QA | 0 |

There is no averaging across security-critical controls.

One security-critical failure yields:

```text
NF-AUTH-03 = NO-GO
```

even if all unrelated tests are green.

---

## 33. Implementation microiterations

D13 freezes ten sequential microiterations.

| ID | Objective | Primary Gate |
|---|---|---|
| `03-A` | Credential contracts + Argon2id adapter + benchmark | Crypto contract PASS |
| `03-B` | Credential ORM + Alembic + repository | PostgreSQL credential Gate |
| `03-C` | JWT service + authentication/login core | JWT/login matrix PASS |
| `03-D` | Refresh persistence model + token crypto | Schema + crypto PASS |
| `03-E` | Session issuance on successful login | Atomic login/session creation |
| `03-F` | Atomic refresh rotation + replay/reuse | Real concurrent PostgreSQL Gate |
| `03-G` | Logout + family revocation | Revocation/race Gate |
| `03-H` | Browser transport + auth HTTP endpoints | Cookie/Origin/CSRF/CORS Gate |
| `03-I` | Integrated real-PostgreSQL security verification | Full security Gate |
| `03-J` | Independent QA / fresh-baseline final audit | Final GO/NO-GO |

### 33.1 `03-A` — Credential / Argon2id Core

Owns:

- `PasswordCredential`;
- `PasswordHasher`;
- concrete Argon2id adapter;
- hash/verify/needs_rehash;
- dummy verification support;
- benchmark;
- controlled crypto errors.

Does not own PostgreSQL schema, JWT, refresh, HTTP, or provisioning.

### 33.2 `03-B` — Credential Persistence

Owns:

- `user_credentials` ORM;
- Alembic migration;
- `CredentialRepository`;
- injected `AsyncSession`;
- insert-only semantics;
- structured duplicate translation;
- compare-and-replace behavior;
- real PostgreSQL verification.

Docker/PostgreSQL preflight is mandatory.

### 33.3 `03-C` — JWT + Authentication Core

Owns:

- authoritative D02-R1 JWT service;
- PS256 issue/validate;
- login authentication core;
- D05 anti-enumeration;
- negative JWT matrix;
- rehash-candidate detection.

Does not expose the final public browser HTTP surface yet.

### 33.4 `03-D` — Refresh Persistence + Cryptography

Owns:

- `refresh_sessions`;
- `refresh_tokens`;
- Alembic migration;
- `RefreshTokenService`;
- CSPRNG 32 bytes;
- canonical Base64URL;
- SHA-256 binary digest;
- schema and crypto evidence.

Does not yet implement rotation/logout/cookie transport.

### 33.5 `03-E` — Login Session Issuance

Owns:

- successful auth → access JWT + S1 + R1;
- atomic session + R1 persistence;
- no secret release before commit;
- post-commit opportunistic rehash transaction.

`SEC-Q02` provisioning remains open.

### 33.6 `03-F` — Atomic Rotation + Reuse

Owns:

- D08 locking;
- session → token lock order;
- same-R1 real concurrency;
- rollback behavior;
- family revocation on reuse;
- at-most-one successor.

PostgreSQL real is mandatory.

### 33.7 `03-G` — Logout + Revocation

Owns:

- current-family logout;
- idempotent semantics;
- known/unknown/missing refresh cases;
- refresh-versus-logout race;
- final revoked-family invariant.

### 33.8 `03-H` — Browser Security / HTTP Surface

Owns:

- auth router and HTTP translation;
- login/refresh/logout routes beneath the configured API prefix;
- exact refresh cookie;
- Origin validation;
- `X-NeuroFin-CSRF: 1`;
- restrictive CORS;
- frontend transport contract;
- cookie clearing.

It must tighten the current repository’s broad CORS method/header configuration rather than inheriting it as final security posture.

### 33.9 `03-I` — Integrated Security Verification

This is primarily evidence work over the published A–H baseline.

It executes the integrated D12 matrix and exact NF-SEC evidence linkage.

Feature development is not silently absorbed here.

A discovered implementation defect requires a controlled corrective microiteration.

### 33.10 `03-J` — Independent QA

Independent QA starts from a published candidate and fresh/clean environment.

It reconstructs critical evidence, including:

- reproducibility;
- PostgreSQL;
- migrations;
- JWT negatives;
- concurrency;
- reuse;
- revocation;
- browser contract;
- full regression;
- source mutation = 0;
- cleanup.

---

## 34. Rule for every implementation microiteration

Each microiteration follows:

```text
published baseline
      ↓
Git guards
      ↓
TDD RED
      ↓
minimal implementation
      ↓
focused GREEN
      ↓
regression
      ↓
quality / boundary / scope audit
      ↓
Architectural Gate
      ↓
controlled commit
      ↓
controlled push / baseline freeze
      ↓
MANDATORY STOP
```

Approval of one microiteration does not authorize the next.

### 34.1 Docker / PostgreSQL preflight

When a property depends on real PostgreSQL semantics, the execution contract must begin with:

```text
Docker Desktop running
docker info PASS
docker compose version PASS
PostgreSQL health = healthy
```

If Docker is unavailable:

```text
ENVIRONMENT / DOCKER NOT READY
→ STOP
```

The agent must not loop, reinterpret the failure as a code defect, or modify code to compensate for an unavailable environment.

---

## 35. Repository integration observations

These are baseline observations used to prevent implementation-time improvisation; they are not claims that `NF-AUTH-03` already exists.

### 35.1 Routing

The current backend mounts the v1 API router using:

```text
app.include_router(api_router, prefix=settings.api_prefix)
```

and the current default prefix is:

```text
/api/v1
```

Therefore the auth HTTP surface shall integrate into the existing router structure and use the configured prefix.

No separate root-level `/auth` versioning system is introduced.

### 35.2 CORS

The current backend already has CORS middleware with configured origins and credentials enabled.

However, its current method/header allowlists are broad.

`03-H` must bring that baseline into conformance with D11’s restrictive auth transport contract.

### 35.3 Existing identity

`NF-AUTH-03` must reuse the existing identity repository and canonical email rules rather than duplicating identity semantics.

---

## 36. Accepted trade-offs

### 36.1 Stateless access-role staleness

A role change does not instantly alter already-issued access JWTs.

Residual role authority may survive until token temporal validation fails.

Compensation:

- ten-minute nominal access lifetime;
- every newly issued access JWT reloads current role.

### 36.2 No access denylist

Logout does not instantly invalidate existing access JWTs.

Compensation:

- short access lifetime;
- refresh family is revoked immediately;
- no additional access token can be obtained from the family.

### 36.3 Strict refresh reuse

A duplicate or replay of a consumed refresh causes family revocation.

This includes the scenario where a valid R2 response was lost and the client retries R1.

This prioritizes replay containment over transparent retry convenience.

### 36.4 Opportunistic rehash

A failure to persist a post-authentication Argon2id rehash does not deny an already valid login.

Compensation:

- old PHC remains valid;
- failure is internally diagnosable without secrets;
- later valid login provides another controlled opportunity.

### 36.5 No full inactivity tracker

The architecture has:

- per-generation refresh expiry;
- absolute session expiry;
- no keepalive-only refresh.

It does not introduce `last_activity_at` or a richer user-activity state machine in this phase.

---

## 37. Change-Control triggers

A Change Control review is required before introducing or altering any of:

- JWT signing algorithm;
- issuer;
- audience;
- mandatory JWT claim set;
- JWT `typ`;
- access-token lifetime;
- JWT leeway;
- refresh-generation lifetime;
- absolute session lifetime;
- access-token denylist;
- multi-key rotation / `kid`;
- JWKS;
- account status;
- new role semantics affecting tokens;
- password pepper;
- refresh HMAC/pepper;
- refresh grace window;
- idempotent consumed-refresh retry;
- logout-all;
- password reset/change/recovery;
- public provisioning;
- OAuth/OIDC/MFA;
- cookie name or security attributes;
- production cross-site frontend topology;
- removal of Origin/CSRF requirements;
- persistence of additional client/device metadata;
- new delete/cascade semantics for auth persistence.

No such change may be introduced as an incidental implementation convenience.

---

## 38. Design consistency result

The approved architecture is internally consistent under the following chain:

```text
Persistent User identity
        ↓
separate PasswordCredential
        ↓
Argon2id verification
        ↓
non-enumerating authentication
        ↓
PS256 short-lived access JWT
        +
stateful refresh family
        ↓
CSPRNG opaque refresh generations
        ↓
hash-only PostgreSQL persistence
        ↓
atomic single-use rotation
        ↓
reuse → family revocation
        ↓
idempotent current-family logout
        ↓
HttpOnly host-only refresh cookie
        ↓
Origin + custom CSRF defense
        ↓
real PostgreSQL + concurrency evidence
        ↓
independent QA
```

The design does not depend on provisioning, business authorization, forecast ownership, MFA, OAuth/OIDC, or ML work.

---

## 39. Written Design Specification Gate

This document is currently:

> **APPROVED AS OFFICIAL**

Official repository design authority:

> **YES**

The User Review Gate is:

> **CLOSED / PASS**

The Implementation Plan is:

> **MATERIALIZED / SELF-REVIEW PASS**

Implementation remains:

> **NOT AUTHORIZED**

Implementation may begin only after the Documentation Gate is closed and a subsequent implementation microiteration is explicitly authorized.

---

## 40. STOP

At this point:

```text
NF-AUTH-03 design decisions            APPROVED
Integral Design Review                 CLOSED / PASS
Written Design Specification           APPROVED AS OFFICIAL
User Review                            CLOSED / PASS
Implementation Plan                    MATERIALIZED / SELF-REVIEW PASS
Documentation Gate                     OPEN / STAGE 1
Implementation                         NOT AUTHORIZED
NF-AUTH-03-A                           NOT STARTED
```

No code, dependencies, migrations, keys, endpoints, or auth tables are authorized by this document alone.

**STOP — complete the Documentation Gate.**

Do not start NF-AUTH-03-A until the documentation baseline has been versioned, reviewed, published, and implementation has been explicitly authorized.

# Multi-Identity Auth and Account Linking Plan

## 1. Background

The current backend auth model is a single local-account model:

- `users.username` is unique and required
- `users.email` is unique and required
- `users.hashed_password` is required
- local login resolves by `username` or `email`
- there is no first-class model for third-party identities
- there is no first-class binding flow for adding another login method to an existing account

This model is sufficient for "local username/email + password" only. It becomes structurally limiting once the product wants:

1. email-based registration
2. WeChat Web login
3. Google login
4. post-registration username/password completion for all entry methods
5. login by username or registered account
6. binding multiple identities to the same account later
7. no forced disruption for existing production users

This document defines the target architecture, the database changes, the auth flow changes, the migration approach, and the implementation sequencing.


## 2. Product Decisions Already Fixed

The following product rules are treated as fixed inputs for this design:

- Three entry methods are required:
  - email registration
  - WeChat Web QR login
  - Google OAuth login
- For all three entry methods, registration is not considered complete until the user fills:
  - `username`
  - `password`
- After registration, the user should be able to log in by:
  - local username + password
  - local email + password
  - WeChat official OAuth
  - Google official OAuth
- Social identities continue to log in through official OAuth, not by reusing provider identifiers as local credentials.
- A user can bind more identities later.
- If an identity or provider-returned email conflicts with an existing account, the system must **not** auto-merge.
- Existing users are treated as "email-identity users".
- Google registration requires email.
- WeChat registration may have no email.
- WeChat scope for v1 is **Web QR login only**, not official account H5, native app, or mini program login.


## 3. Current-State Analysis of This Repository

### 3.1 Current auth data model

The current user/auth schema is centered on `app/service/auth/database/models.py`.

Relevant facts:

- `users.email` is currently `unique=True, nullable=False`
- `users.hashed_password` is currently `nullable=False`
- there is no `oauth identity` or `linked account` table
- session and refresh-token logic is already independent enough and should be preserved

### 3.2 Current local auth behavior

The current backend already supports:

- `POST /auth/register`
- `POST /auth/login`
- local login by `username` or `email`
- session-based access/refresh token model

The current register flow is direct account creation. There is no formal "pending identity verified, waiting to complete username/password" state.

### 3.3 Current migration reality

The repository does not use Alembic. The auth DB is largely created by:

- SQLAlchemy `Base.metadata.create_all(...)`
- ad hoc SQLite migration helpers

This means schema evolution must be implemented carefully. Adding tables is easy. Changing existing column nullability or constraints is not automatic and may require explicit SQLite migration logic.


## 4. Design Principle

### 4.1 Core principle

Use:

- `users` as the **account table**
- `user_auth_identities` as the **login-identity table**

Do **not** keep extending `users` with provider-specific columns such as:

- `google_sub`
- `google_email`
- `wechat_openid`
- `wechat_unionid`

That would be a short-term shortcut, but not a durable design.

### 4.2 Why this is the right practice here

This repository already has a stable notion of "user account" used by:

- sessions
- permissions
- analytics
- admin pages
- custom data ownership

So the cleanest long-term design is:

- keep `users.id` as the main stable account id
- keep `users.username` as the stable in-app public identity
- keep `users.hashed_password` as the account-level local password
- move provider-linked login identities into a separate table

This provides the right balance between:

- correctness
- extensibility
- backward compatibility
- migration safety


## 5. Target Database Design

## 5.1 `users` remains the account table

Keep `users` as the stable account record.

### Keep as-is conceptually

- `id`
- `username`
- `hashed_password`
- `role`
- `status`
- `created_at`
- `updated_at`
- session-related fields
- usage/analytics related fields

### Change in meaning

- `email` should become a **primary contact email snapshot**, not the sole auth source of truth
- `is_verified` should become a **primary-email verification compatibility flag**

### Schema target

- `username`: `UNIQUE NOT NULL`
- `hashed_password`: `NOT NULL`
- `email`: **nullable**
- `is_verified`: keep for compatibility in phase 1

### Why `users.email` should become nullable

Because:

- Google typically provides email, but WeChat Web login may not
- forcing all accounts to have email no longer matches reality
- storing fake emails for WeChat-only accounts is poor design and creates future cleanup problems

### Why not remove `users.email` immediately

Because many existing services, admin endpoints, and analytics paths already read `users.email`.
Removing it in phase 1 would create unnecessary blast radius.

Phase 1 keeps it as a compatibility field and mirrors it from the primary verified email identity when one exists.


## 5.2 New table: `user_auth_identities`

This is the central new table.

Each row represents one login-capable identity bound to one account.

### Proposed columns

- `id INTEGER PRIMARY KEY`
- `user_id INTEGER NOT NULL`
- `provider VARCHAR(20) NOT NULL`
  - allowed values in v1:
    - `email`
    - `google`
    - `wechat`
- `provider_subject VARCHAR(255) NULL`
  - Google: OpenID `sub`
  - WeChat Web: `openid`
  - email: null
- `identifier VARCHAR(255) NULL`
  - for `email`, stores the original email
  - for Google/WeChat, may store a provider-facing label if needed
- `identifier_normalized VARCHAR(255) NULL`
  - email lowercased and normalized
  - may be null for Google/WeChat
- `email_claim VARCHAR(255) NULL`
  - Google-provided email if any
  - WeChat usually null
- `display_name VARCHAR(255) NULL`
  - optional provider nickname snapshot
- `avatar_url VARCHAR(500) NULL`
  - optional provider avatar snapshot
- `is_verified BOOLEAN NOT NULL DEFAULT 0`
- `is_primary BOOLEAN NOT NULL DEFAULT 0`
- `is_enabled BOOLEAN NOT NULL DEFAULT 1`
- `linked_at DATETIME NOT NULL`
- `last_login_at DATETIME NULL`
- `last_used_ip VARCHAR(45) NULL`
- `metadata_json TEXT NULL`
  - provider-specific extra fields such as:
    - Google hosted domain
    - WeChat unionid

### Proposed constraints

- foreign key: `user_id -> users.id`
- unique: `(provider, provider_subject)`
- unique: `(provider, identifier_normalized)`
- unique: `(user_id, provider)`

### Notes on uniqueness

For v1, enforce one identity per provider per user:

- max one email identity per user
- max one Google identity per user
- max one WeChat identity per user

This is the correct tradeoff for now. It is simple and sufficient.


## 5.3 New table: `auth_email_verifications`

This table stores email verification flows.

It replaces the current "re-use access token as email verification token" pattern.

### Proposed columns

- `id INTEGER PRIMARY KEY`
- `user_id INTEGER NULL`
- `purpose VARCHAR(30) NOT NULL`
  - values:
    - `register_email`
    - `bind_email`
    - `change_email`
- `email VARCHAR(255) NOT NULL`
- `token_hash VARCHAR(255) NOT NULL`
- `expires_at DATETIME NOT NULL`
- `consumed_at DATETIME NULL`
- `created_at DATETIME NOT NULL`
- `request_ip VARCHAR(45) NULL`
- `user_agent VARCHAR(255) NULL`
- `payload_json TEXT NULL`

### Why a dedicated table is worth it

Because email verification is not the same thing as an access token.

Dedicated storage makes it easier to support:

- single-use links
- expiration
- resend logic
- rate limiting
- auditability
- future password reset and email change patterns


## 5.4 Redis-based transient flow state

Do not create persistent DB tables for short-lived flow state.

Use Redis keys:

- `oauth_state:{nonce}`
- `oauth_pending:{ticket}`
- `bind_pending:{ticket}`

### Stored values

`oauth_state:{nonce}`:

- provider
- action: `register` or `bind`
- original redirect target if needed
- created_at

`oauth_pending:{ticket}`:

- provider
- provider subject
- email claim
- email verified by provider
- provider profile snapshot
- created_at

`bind_pending:{ticket}`:

- current user id
- provider
- provider subject
- provider claims
- created_at

### TTL

- state: 5 to 10 minutes
- pending register/bind ticket: 10 to 15 minutes


## 6. Registration and Login Flow Design

## 6.1 Email registration flow

This becomes a two-step registration.

### Step A: start registration

Endpoint:

- `POST /auth/register/email/start`

Input:

- `email`

Behavior:

- normalize email
- reject if email identity already exists
- create one verification record in `auth_email_verifications`
- send email verification link

No `users` row is created yet.

### Step B: verify link

Endpoint:

- `GET /auth/register/email/verify`

Behavior:

- validate token
- mark verification record consumed
- issue a short-lived `register_ticket`

At this point the identity proof is done, but the account is not yet complete.

### Step C: complete registration

Endpoint:

- `POST /auth/register/complete`

Input:

- `register_ticket`
- `username`
- `password`

Behavior:

- validate ticket from Redis
- ensure username is unique
- create `users`
- create `user_auth_identities(provider=email)`
- set `users.email`
- set `users.is_verified = true`
- create session + access/refresh tokens


## 6.2 Google registration/login flow

### Step A: start

- `GET /auth/oauth/google/start`

Behavior:

- create OAuth state
- redirect to Google authorization URL

### Step B: callback

- `GET /auth/oauth/google/callback`

Behavior:

- validate OAuth state
- exchange code with Google
- parse:
  - `sub`
  - `email`
  - `email_verified`
  - profile name/avatar if desired

### Resolution rules

If a Google identity already exists:

- log in directly

If no Google identity exists:

- if returned email matches an existing email identity:
  - reject auto-registration
  - return conflict result:
    - this email already belongs to an existing account
    - user must log in to that account and bind Google manually
- otherwise:
  - create `register_ticket`
  - user must complete `username + password`

### Completion

Use the same:

- `POST /auth/register/complete`

The ticket tells the backend this is a Google-pending registration.


## 6.3 WeChat registration/login flow

### Step A: start

- `GET /auth/oauth/wechat/start`

Behavior:

- create OAuth state
- redirect to official WeChat Web QR authorization URL

### Step B: callback

- `GET /auth/oauth/wechat/callback`

Behavior:

- validate state
- exchange code for WeChat user identity
- obtain:
  - `openid`
  - `unionid` if available
  - profile snapshot if available

### Resolution rules

If the WeChat identity already exists:

- log in directly

If it does not exist:

- create a `register_ticket`
- user must complete `username + password`

Because WeChat may not provide email, this flow must support accounts with:

- username
- password
- no email


## 6.4 Local login flow

Keep local login in one endpoint for compatibility:

- `POST /auth/login`

Input stays compatible with:

- `username`
- `password`

or more precisely:

- `identifier`
- `password`

### Resolution order

1. try `users.username`
2. if not found, try `user_auth_identities(provider=email, identifier_normalized=...)`
3. validate account password against `users.hashed_password`

### Important rule

Third-party identities do **not** bypass provider OAuth by using local password directly.

That means:

- Google login remains Google OAuth
- WeChat login remains WeChat OAuth
- local password login remains username/email only


## 7. Binding Flows

## 7.1 Bind Google

Endpoints:

- `GET /auth/bind/google/start`
- `GET /auth/bind/google/callback`

Behavior:

- user must already be authenticated
- start generates OAuth state for `action=bind`
- callback resolves Google identity

If Google identity is already bound to another user:

- reject with conflict

If safe:

- create Google identity row for current user
- optionally sync profile snapshot


## 7.2 Bind WeChat

Endpoints:

- `GET /auth/bind/wechat/start`
- `GET /auth/bind/wechat/callback`

Same conflict behavior as Google.


## 7.3 Bind email

Endpoints:

- `POST /auth/bind/email/start`
- `GET /auth/bind/email/verify`

Behavior:

- user enters email
- system sends verification link
- verification completion creates or updates the email identity
- if account has no primary email yet, this email becomes primary


## 7.4 Identity listing

Endpoint:

- `GET /auth/me/identities`

Returns:

- providers currently linked
- primary flag
- verification flag
- lightweight profile snapshot


## 8. Conflict Rules

These rules are intentionally strict.

### 8.1 No automatic account merge

If a third-party login returns an email that belongs to an existing account, the backend must **not** automatically merge or attach that identity.

Instead:

- stop the self-registration flow
- return a structured conflict response
- tell the user to sign in to the existing account first and then bind

### 8.2 Existing identity already owned by another user

If a provider subject is already linked to another user:

- reject binding
- reject new registration

### 8.3 Why strict conflict rules are correct

Because automatic merge is one of the highest-risk mistakes in account systems.

It is especially dangerous when:

- provider emails are reused or stale
- users made multiple accounts historically
- verification rules changed over time

Strict no-auto-merge is the right policy for this product stage.


## 9. Backward Compatibility Strategy

## 9.1 Existing users

Treat all current users as existing email-based local accounts.

Migration behavior:

- create an `email` identity for every existing `users.email`
- carry over `users.is_verified`
- set identity `is_primary = true`

Existing users keep:

- username login
- email login
- password login
- existing sessions

No forced re-registration is required.


## 9.2 JWT and session compatibility

Do not change the session model in this project phase.

Keep:

- access token structure
- refresh/session logic
- `sub = username`

Reason:

- many existing auth dependencies and admin features already assume `username` in JWT
- changing JWT subject and identity lookup at the same time would enlarge risk significantly


## 9.3 Compatibility use of `users.email`

Phase 1 keeps `users.email` as a compatibility projection.

Rules:

- if user has a primary email identity, mirror it into `users.email`
- if user has no email identity, `users.email = null`
- existing admin/search logic can continue using `users.email`

Later, the codebase can gradually move to querying `user_auth_identities`.


## 10. API Changes

## 10.1 New endpoints

Public:

- `POST /auth/register/email/start`
- `GET /auth/register/email/verify`
- `POST /auth/register/complete`
- `GET /auth/oauth/google/start`
- `GET /auth/oauth/google/callback`
- `GET /auth/oauth/wechat/start`
- `GET /auth/oauth/wechat/callback`

Authenticated:

- `GET /auth/bind/google/start`
- `GET /auth/bind/google/callback`
- `GET /auth/bind/wechat/start`
- `GET /auth/bind/wechat/callback`
- `POST /auth/bind/email/start`
- `GET /auth/bind/email/verify`
- `GET /auth/me/identities`

## 10.2 Existing endpoints to keep

- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/refresh`
- `GET /auth/me`

## 10.3 Existing endpoint that should become compatibility-only

- `POST /auth/register`

Recommended treatment:

- keep it temporarily for legacy clients
- internally route it into the new email registration path if needed
- eventually mark deprecated


## 11. Required Service-Layer Refactor

This is not a tiny route-only change. The following auth subsystems need service-level upgrades.

### 11.1 User lookup and login resolution

Current:

- directly query `users.username` or `users.email`

Target:

- resolve login through:
  - `username`
  - `email identity`
- then load owning `user`

### 11.2 Registration state machine

Current:

- register means immediately creating `users`

Target:

- registration is split into:
  - identity proof
  - completion with username/password

### 11.3 Email verification

Current:

- simplified token approach

Target:

- dedicated verification record
- purpose-aware validation

### 11.4 Social identity integration

Need dedicated service helpers for:

- start Google OAuth
- handle Google callback
- start WeChat OAuth
- handle WeChat callback
- resolve conflict rules
- create bind/register tickets


## 12. Database Migration Plan

Because this repository does not use Alembic, migration must be explicit.

## 12.1 Phase A: additive migration

Safe additions first:

1. create `user_auth_identities`
2. create `auth_email_verifications`
3. add indexes
4. backfill email identities for existing users

These changes are straightforward.

## 12.2 Phase B: `users.email` compatibility migration

Changing `users.email` to nullable is harder under SQLite.

Recommended migration approach:

1. inspect current schema
2. create a new temporary table `users_new` with desired schema
3. copy existing data
4. drop old `users`
5. rename `users_new` to `users`
6. recreate indexes and constraints

This is safer than relying on unsupported SQLite `ALTER COLUMN` semantics.

## 12.3 Phase C: code cutover

After tables exist and data is backfilled:

- switch auth flows to read/write new identity table
- keep `users.email` synchronized


## 13. Logging, Analytics, and Admin Impact

These are not blockers for phase 1, but they should be included in implementation scope.

### 13.1 Login logs

Add `login_method` or equivalent logging metadata:

- `local_username`
- `local_email`
- `google`
- `wechat`

### 13.2 Admin user search

Keep admin search working with:

- username
- primary email

Second phase can extend search to provider identity metadata if needed.

### 13.3 `/auth/me`

Eventually should return:

- user core info
- linked identities summary


## 14. Security Considerations

### 14.1 Why username/password completion is account-level, not provider-level

The local password belongs to the account, not to Google or WeChat.

That means:

- one account
- one local password
- multiple linked external identities

This is the correct mental model and the correct storage model.

### 14.2 Why provider login must remain provider login

Do not allow:

- WeChat account identifier + local password
- Google account identifier + local password

as substitute flows.

That would blur identity boundaries and make future auditing and security harder.

### 14.3 Why no automatic merge

Automatic merge sounds user-friendly but creates serious ownership mistakes.

Strict manual linking is the safer default.


## 15. Test Plan

The implementation must include tests for all of the following:

### 15.1 Migration and compatibility

- existing user gets one email identity after migration
- existing user can still log in by username
- existing user can still log in by email
- existing sessions remain valid

### 15.2 Email registration

- email start sends verification
- valid verification produces register ticket
- complete registration creates user and email identity
- duplicate email is rejected
- duplicate username is rejected
- expired verification token is rejected
- reused verification token is rejected

### 15.3 Google registration/login

- first-time Google login with unique email produces register ticket
- Google completion creates user and identity
- repeated Google login logs in directly
- Google email conflict rejects auto-merge

### 15.4 WeChat registration/login

- first-time WeChat login produces register ticket
- completion creates user without email
- repeated WeChat login logs in directly
- WeChat identity conflict is rejected

### 15.5 Binding

- logged-in user binds Google successfully
- logged-in user binds WeChat successfully
- logged-in user binds email successfully after verification
- binding identity already owned by another user is rejected

### 15.6 Local login

- local login by username works
- local login by email identity works
- provider identity is not accepted as a local login identifier


## 16. Suggested Implementation Order

This is the recommended order if/when the team actually implements this plan.

### Phase 1: DB and core identity model

- add new tables
- add migration helper
- backfill existing users

### Phase 2: local auth compatibility refactor

- update login resolution to use identity table
- keep existing `/auth/login`

### Phase 3: email registration v2

- email start
- email verify
- register complete

### Phase 4: Google auth

- start/callback
- registration completion
- bind flow

### Phase 5: WeChat auth

- start/callback
- registration completion
- bind flow

### Phase 6: admin and analytics adaptation

- login_method logging
- identity listing
- admin display improvements


## 17. Scope Boundaries for v1

To keep the first implementation realistic, v1 should **not** include:

- user self-service account merge
- multiple emails per user
- multiple Google accounts bound to one user
- multiple WeChat accounts bound to one user
- provider-specific password login
- WeChat mini program login
- native mobile provider login


## 18. Final Recommendation

The best-practice path for this repository is:

1. keep `users` as the stable account table
2. add `user_auth_identities` as the source of truth for login identities
3. add `auth_email_verifications` for email verification flows
4. use Redis for transient OAuth/register/bind tickets
5. keep JWT/session model unchanged in phase 1
6. keep `users.email` as a compatibility mirror field in phase 1
7. forbid automatic account merge

This gives the project:

- correct multi-identity modeling
- reasonable backward compatibility
- lower rollout risk for production users
- a clean path to future auth expansion


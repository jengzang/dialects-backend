# Multi-Identity Auth and Account Linking Plan

## Status Snapshot (updated 2026-05-12)

This section records the implementation status of this plan against the current repository state so the document remains an execution guide rather than a stale design note.

### Overall completion estimate

- overall plan completion: roughly 70% to 78%
- if judged only by already-usable end-user auth capabilities: roughly 78% to 85%
- if judged strictly against the full v1 design, security rules, endpoint contract normalization, and broader verification expectations: still incomplete

### Completed or mostly completed

- identity-oriented schema foundation is in place:
  - `users.email` is now nullable
  - `user_auth_identities` exists
  - `auth_action_tokens` exists and is currently used for verification/reset/register-email actions
  - explicit SQLite migration helpers and email-identity backfill are implemented
- local auth compatibility refactor is mostly done:
  - local login still uses `POST /api/auth/login`
  - local login resolution supports `username + password`
  - local login resolution supports `email identity + password`
  - `users.email` is synchronized as a compatibility projection
- email/account recovery features are implemented in practical form:
  - resend verification
  - verify email
  - forgot password
  - reset password
  - authenticated change password
  - authenticated change email + reverification
- email registration v2 now exists in practical backend form:
  - `POST /api/auth/register-email`
  - `GET /api/auth/verify-email-registration`
  - `POST /api/auth/complete-email-registration`
  - token storage still uses `auth_action_tokens`
- Google support is partially implemented and already usable in practice:
  - Google login decision endpoint exists
  - Google registration completion exists
  - Google bind exists
- WeChat support now exists in minimal backend v1 form:
  - WeChat login decision endpoint exists
  - WeChat registration completion exists
  - WeChat bind exists
  - current backend shape accepts client-provided `access_token + openid` and validates userinfo server-side
- identity/provider visibility is partially implemented:
  - provider listing exists
  - `/api/auth/me` already returns linked provider summary
  - provider listing exposes `can_unbind=false`, `can_replace`, and `replacement_action`
- v1 unlink policy is enforced in runtime behavior:
  - the legacy provider-unbind endpoint remains compatibility-only
  - runtime behavior is hard-blocked to "replace, not remove"
- high-risk protections are partially in place:
  - change-password requires current password
  - change-email requires current password
  - Google bind requires a fresh recent authenticated session
  - WeChat bind requires a fresh recent authenticated session
- auth UTC handling was partially normalized in the auth module to use a shared helper rather than scattered `datetime.utcnow()` calls

### Important implementation deviations from this document

The current codebase does not fully match the original planned shape. These differences must be treated as deliberate temporary deviations unless later normalized back into the plan.

1. Email verification storage
   - planned here: dedicated `auth_email_verifications` table
   - current implementation: generalized `auth_action_tokens`
   - effect: functional coverage exists, but the storage model differs from this document

2. Google flow shape
   - planned here: OAuth `start` / `callback` endpoints with transient flow state
   - current implementation: backend accepts Google `id_token` directly from the client
   - effect: Google capability exists, but not in the exact planned architecture

3. WeChat flow shape
   - planned here: official Web QR OAuth start/callback flow with transient state
   - current implementation: backend accepts client-provided `access_token + openid` and validates userinfo server-side
   - effect: WeChat capability now exists, but not in the exact planned architecture and not yet as the full official Web QR backend contract

4. Email registration v2
   - planned here: `start -> verify -> complete` registration state machine with explicit long-term state handling design
   - current implementation: the three practical backend routes now exist, but the design is still lighter than the original planned state-machine / transient-state framing
   - effect: practical v2 flow exists, but the implementation should either be normalized to the full design or the document should later be revised to bless the practical route shape

5. Unbind policy
   - planned here: v1 forbids naked unlink; product rule is replace, not remove
   - current implementation: the existing provider-unbind endpoint is hard-blocked in v1 and returns a business rejection instead of removing the linked identity
   - effect: runtime behavior now matches the stricter documented rule, though the API surface still exists and may be cleaned up later if desired

6. Google email policy
   - planned here: malformed or unusable Google email should not necessarily block v1 continuation
   - current implementation: Google registration currently requires provider email
   - effect: implementation is stricter than this document

### Major unfinished work

- replacement / rebind API contract is still transitional and not fully normalized end-to-end, although backend runtime policy is now more consistent
- Redis-based transient register / bind / OAuth state handling is not implemented in the planned form
  - important environment constraint: this repository has different runtime modes
    - local `MINE` / `EXE` development on this machine does not have a real Redis service and relies on fake-Redis / dump-style behavior in related parts of the codebase
    - deployed `WEB` mode is the place where real Redis-backed behavior can be assumed
  - implication: any future transient-state implementation must either
    - degrade cleanly to DB/token-table/local fallback behavior for local development, or
    - be explicitly scoped as a WEB-only production capability with local simulation coverage
- Google and WeChat do not yet use the full planned official OAuth start/callback contract shape
- tests are still far from the coverage listed in this document
- admin / analytics adaptation is only partially implemented
- login-method analytics/logging does not appear fully integrated yet

### Remaining work breakdown with priority and rough estimate

P0 — needed before claiming the document's v1 architecture is truly landed
- freeze provider-management wording and frontend contract around replacement / rebind
  - backend runtime is already close, but frontend wording and any remaining old unlink assumptions still need one final alignment pass
  - estimate: 0.5 day
- choose and document the v1 architecture decision for Google/WeChat + transient state
  - either implement official `start/callback` + transient-state handling
  - or explicitly bless the current practical client-token backend shape as the chosen v1 architecture
  - estimate:
    - document-only decision path: 0.5 day
    - real implementation path: 2 to 5 days

P1 — important for robustness and production completeness
- implement or formally defer Redis/transient-state handling in a way that respects runtime modes
  - local MINE/EXE must not assume a real Redis dependency
  - WEB mode may use real Redis
  - estimate:
    - fallback-friendly minimal implementation / explicit defer plan: 0.5 to 1 day
    - full Redis-backed production design with local fallback/simulation: 1 to 2 days beyond the OAuth flow work
- broaden auth test coverage
  - route/integration coverage for provider conflict, register/bind/replace paths, and failure branches
  - estimate: 0.5 to 1.5 days
- finish admin / analytics adaptation
  - estimate: 0.5 to 1.5 days

P2 — cleanup / consistency / long-tail design debt
- reconcile later sections of this document whose wording still reflects older unlink or original OAuth assumptions
- decide whether the legacy DELETE provider endpoint should remain as compatibility-only surface or later be removed entirely
- revisit Google email policy mismatch if product still wants the looser v1 rule documented here
- estimate: 0.5 to 1 day
### Current `/api/auth/providers` and `/api/auth/me` contract reality

The backend contract is now stable enough to describe explicitly, even though some naming remains transitional.

- `GET /api/auth/providers` returns a list of `AuthProviderStatus`
- `GET /api/auth/me` returns `UserMeResponse` with `auth_providers: AuthProviderStatus[]`
- each `AuthProviderStatus` currently includes:
  - `provider`
  - `email`
  - `display_name`
  - `is_verified`
  - `is_primary`
  - `linked_at`
  - `last_login_at`
  - `profile_picture`
  - `can_unbind`
  - `can_replace`
  - `replacement_action`
- current runtime semantics are:
  - `can_unbind` is always `false` in v1
  - `can_replace` is `true` for providers that have a supported replacement/bind path in the current backend
  - `replacement_action` is the machine hint the frontend should use to route the user to the right replacement flow
    - email -> `change_email`
    - google -> `bind_google`
    - wechat -> `bind_wechat`
- the legacy `DELETE /api/auth/providers/{provider}` endpoint still exists for compatibility, but v1 runtime policy hard-rejects removal for known providers and only preserves the endpoint as a compatibility surface

Implication:
- frontend should render provider management in terms of replace/rebind actions, not unlink/remove actions
- this document still uses some older unlink language in later sections; when those sections are executed, they should be interpreted through the runtime rule above unless deliberately redesigned

### Phase-by-phase progress view

- Phase 1: DB and core identity model
  - mostly complete
- Phase 2: local auth compatibility refactor
  - mostly complete
- Phase 3: email registration v2
  - materially advanced and usable in practical backend form, but still not fully normalized to the original design language
- Phase 4: Google auth
  - partially complete and usable, but architecture differs from the original plan
- Phase 5: WeChat auth
  - minimally implemented and usable in backend form, but not yet in the original planned Web QR OAuth architecture
- Phase 6: admin and analytics adaptation
  - partially complete

### Recommended next implementation priority

Recommended next step:
- first freeze and document the already-shipping provider-management contract around "replace, not remove"
  - current backend runtime now consistently hard-rejects unlink for known providers
  - current provider listing already exposes `can_unbind=false`, `can_replace`, and `replacement_action`
  - frontend and product copy should treat provider management as replacement / bind guidance, not delete semantics
- then decide whether to:
  - implement full official Google/WeChat OAuth start/callback + transient-state handling, or
  - explicitly revise this document to accept the current practical client-token backend route shape as the chosen v1 architecture
- after that, finish admin / analytics adaptation and broaden auth test coverage

Why this is the next best step:
- full-app import/bootstrap verification is no longer blocked by the previous issues discovered during this session
- runtime provider policy is now stricter and more internally consistent than before, so the next risk is documentation/frontend drift rather than backend ambiguity alone
- further auth work will be safer once the replacement contract and chosen v1 OAuth architecture are both made explicit

After that, the recommended order becomes:
1. freeze provider-management wording and frontend contract around replacement / rebind
2. either implement the planned official OAuth/transient-state architecture or formally bless the current practical route shape in this document
3. then finish admin / analytics adaptation and broader auth test coverage
4. finally, revisit any remaining doc sections whose original unlink/OAuth assumptions no longer match the chosen implementation

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
- Google registration should request email, but a malformed or unusable provider-returned email does not block account creation in v1.
- WeChat registration may have no email.
- WeChat scope for v1 is **Web QR login only**, not official account H5, native app, or mini program login.
- Web/PC is the only supported WeChat v1 scenario. Mobile web behavior is not guaranteed in v1.
- Email registration should support both verification links and verification codes long-term; v1 starts with verification links.
- Local password login remains:
  - username + password
  - email + password
- Username and password validation rules remain the current backend rules in v1; this project does not redefine them.
- Registration completion should create a logged-in session immediately.
- `users.email` is only a compatibility projection / primary contact snapshot in phase 1. `user_auth_identities` is the source of truth for login identities.
- Each user may have at most one identity per provider in v1:
  - one email identity
  - one Google identity
  - one WeChat identity
- Identity removal does not support naked unlink in v1. The product rule is "replace, not remove":
  - direct unlink is not allowed
  - email supports replacement in v1
  - Google/WeChat support bind in v1, but not a full self-service replacement flow yet
- Conflict responses should be structured and explicit:
  - no auto-merge
  - return a clear business conflict code
  - include a suggested next action such as `login_then_bind`
- If an old local account already owns an email, auto-merge remains forbidden even if that old email was never verified.
- High-risk account/identity operations require the current password.
- Forgot/reset-password scope is included in v1.
- Account recovery-related entry points may come from email, Google, or WeChat, but provider-assisted recovery must still follow the final security rules of this document.


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

- `POST /api/auth/register`
- `POST /api/auth/login`
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

- `email` should become a **current bound email / contact email projection**, not the sole auth source of truth
- `is_verified` should remain a **compatibility field**, not the new cross-provider source of truth for verification state

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

Phase 1 keeps it as a compatibility field and mirrors it from the current bound email identity when one exists.


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

### Note on `is_primary`

V1 does not define a global "primary identity" concept across all providers.

If `is_primary` is kept in the schema, it should only be meaningful for the email identity / primary contact email projection.

Google and WeChat identities should not rely on `is_primary` semantics in v1.


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

`oauth_state` should be strictly single-use.

`oauth_pending:{ticket}`:

- provider
- provider subject
- email claim
- email verified by provider
- provider profile snapshot
- created_at

This ticket should support retry for correctable completion failures while it remains valid, but it must be consumed and invalidated immediately after successful registration completion.

`bind_pending:{ticket}`:

- current user id
- provider
- provider subject
- provider claims
- created_at

This ticket should support retry for correctable completion failures while it remains valid, but it must be consumed and invalidated immediately after successful bind/replacement completion.

### TTL

- state: 5 to 10 minutes
- pending register/bind ticket: 30 minutes

### Expiration policy

- email registration expiration may offer resend/restart behavior
- OAuth register/bind expiration requires restarting the flow
- the state nonce is single-use
- register/bind pending tickets may be retried only until a successful completion, after which they are invalidated immediately


## 6. Registration and Login Flow Design

## 6.1 Email registration flow

This becomes a two-step registration.

### Step A: start registration

Endpoint:

- `POST /api/auth/register/email/start`

Input:

- `email`

Behavior:

- normalize email
- reject if email identity already exists
- create one verification record in `auth_email_verifications`
- send email verification link

V1 uses email verification links. Verification-code support is a later extension, not part of the initial implementation.

No `users` row is created yet.

### Step B: verify link

Endpoint:

- `GET /api/auth/register/email/verify`

Behavior:

- validate token
- mark verification record consumed
- issue a short-lived `register_ticket`

The frontend-facing Web pattern for v1 is:

- backend verifies the token
- backend issues `register_ticket`
- backend redirects the browser to the frontend completion page

At this point the identity proof is done, but the account is not yet complete.

### Step C: complete registration

Endpoint:

- `POST /api/auth/register/complete`

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

If completion fails due to username conflict or another correctable validation issue, the `register_ticket` remains usable until expiration so the user can retry.


## 6.2 Google registration/login flow

### Step A: start

- `GET /api/auth/oauth/google/start`

Behavior:

- create OAuth state
- redirect to Google authorization URL

### Step B: callback

- `GET /api/auth/oauth/google/callback`

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

Google-specific v1 notes:

- Google login normally expects an email claim
- `email_verified` is not required for account creation in v1
- if the returned email is malformed, empty, or otherwise unusable, v1 may still allow account creation and later email binding
- provider profile snapshot fields such as `display_name` and `avatar_url` should be refreshed on successful third-party login

### Completion

Use the same:

- `POST /api/auth/register/complete`

The ticket tells the backend this is a Google-pending registration.

For the Web flow in v1, callback handling should redirect to a frontend completion page rather than return a raw API-style JSON callback response.


## 6.3 WeChat registration/login flow

### Step A: start

- `GET /api/auth/oauth/wechat/start`

Behavior:

- create OAuth state
- redirect to official WeChat Web QR authorization URL

### Step B: callback

- `GET /api/auth/oauth/wechat/callback`

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

WeChat v1 scope note:

- supported scenario: website / desktop-oriented Web QR login
- unsupported in v1: mini program login, native mobile provider login
- mobile web behavior is not guaranteed
- provider profile snapshot fields such as `display_name` and `avatar_url` should be refreshed on successful third-party login


## 6.4 Local login flow

Keep local login in one endpoint for compatibility:

- `POST /api/auth/login`

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

- `GET /api/auth/bind/google/start`
- `GET /api/auth/bind/google/callback`

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

- `GET /api/auth/bind/wechat/start`
- `GET /api/auth/bind/wechat/callback`

Same conflict behavior as Google.


## 7.3 Bind email

Endpoints:

- `POST /api/auth/bind/email/start`
- `GET /api/auth/bind/email/verify`

Behavior:

- user enters email
- system sends verification link
- verification completion creates or updates the email identity
- if account has no current bound email yet, this email becomes the current bound email

V1 binding/change policy:

- email may be replaced, but not naked-unlinked
- when email is replaced, the new verified email takes over immediately and the old email stops being a bound identity
- change-email is in scope for v1


## 7.4 Identity listing

Endpoint:

- `GET /api/auth/me/identities`

Returns:

- providers currently linked
- email-primary flag semantics only where applicable
- verification flag
- lightweight profile snapshot

Recommended v1 fields include:

- `provider`
- `is_primary`
- `is_verified`
- `linked_at`
- `display_name`
- `avatar_url`
- `can_unbind` (always `false` in v1)
- `can_replace`
- `replacement_action` such as `change_email`, `bind_google`, or `bind_wechat`

In v1, `is_primary` should be interpreted only for the email identity / primary contact email projection, not as a cross-provider primary identity flag.

Clients should render provider management from capability fields instead of inferring available actions from HTTP verbs. In v1, linked identities are replace/bind targets, not removable items.


## 8. Conflict Rules

These rules are intentionally strict.

### 8.1 No automatic account merge

If a third-party login returns an email that belongs to an existing account, the backend must **not** automatically merge or attach that identity.

Instead:

- stop the self-registration flow
- return a structured conflict response
- tell the user to sign in to the existing account first and then bind

The structured response should carry both:

- a stable business conflict code
- a suggested next action such as `login_then_bind`

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
- carry over `users.is_verified` exactly as-is
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

For WeChat-origin accounts that have no email identity, the compatibility field `users.is_verified` may still be set to `true` after successful WeChat registration/login because there is no pending email-verification gate for that account shape in v1.


## 9.3 Compatibility use of `users.email`

Phase 1 keeps `users.email` as a compatibility projection.

Rules:

- if user has a current bound email identity, mirror it into `users.email`
- if user has no email identity, `users.email = null`
- existing admin/search logic can continue using `users.email`

Later, the codebase can gradually move to querying `user_auth_identities`.


## 10. API Changes

## 10.1 New endpoints

Public:

- `POST /api/auth/register/email/start`
- `GET /api/auth/register/email/verify`
- `POST /api/auth/register/complete`
- `GET /api/auth/oauth/google/start`
- `GET /api/auth/oauth/google/callback`
- `GET /api/auth/oauth/wechat/start`
- `GET /api/auth/oauth/wechat/callback`

Authenticated:

- `GET /api/auth/bind/google/start`
- `GET /api/auth/bind/google/callback`
- `GET /api/auth/bind/wechat/start`
- `GET /api/auth/bind/wechat/callback`
- `POST /api/auth/bind/email/start`
- `GET /api/auth/bind/email/verify`
- `GET /api/auth/me/identities`
- `POST /api/auth/password/forgot/start`
- `POST /api/auth/password/forgot/complete`
- `POST /api/auth/password/change`
- `POST /api/auth/password/reset-authenticated`

## 10.2 Existing endpoints to keep

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/auth/refresh`
- `GET /api/auth/me`

## 10.3 Existing endpoints that should become compatibility-only

- `POST /api/auth/register`
- `DELETE /api/auth/providers/{provider}`

Recommended treatment:

- keep them temporarily for legacy clients
- internally route legacy registration into the new email registration path if needed
- keep provider DELETE hard-blocked in v1 because the product policy is replace/rebind, not unlink
- eventually mark deprecated once clients use explicit replacement actions


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
- current bound email

Second phase can extend search to provider identity metadata if needed.

### 13.3 `/api/auth/me`

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

### 14.4 High-risk operations require current password

For v1, high-risk account operations require the current local password. This includes identity-sensitive changes such as change-email and replacement-style identity changes.

This rule intentionally does not grant an exception merely because the user can still log in through a bound Google or WeChat account.

### 14.5 Password reset terminology

This document distinguishes:

- `change password`: user knows the current password and changes it from an authenticated session
- `forgot password`: user proves ownership through a recovery flow such as email
- `authenticated password reset`: user is already authenticated through an allowed entry path and resets the local password under the product's security rules

### 14.6 Fresh-session requirement for identity binding

Binding Google or WeChat should require not only an authenticated session but also a fresh recent authentication window in v1.

This is intended to reduce the risk of someone using an old but still-valid session on an unattended device to silently attach a new identity.


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
- successful completion creates a logged-in session immediately
- duplicate email is rejected
- duplicate username is rejected
- expired verification token is rejected
- reused verification token is rejected
- expired register ticket can be retried only by restarting/resending according to the flow rules

### 15.3 Google registration/login

- first-time Google login with unique email produces register ticket
- Google completion creates user and identity
- repeated Google login logs in directly
- Google email conflict rejects auto-merge
- Google `email_verified` is not required for registration in v1
- malformed/unusable Google email claim still follows the chosen v1 continuation policy

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
- direct unlink is rejected in v1
- email replacement succeeds and old email immediately stops being bound

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
- keep existing `/api/auth/login`

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
- naked identity unlink
- full self-service Google replacement flow
- full self-service WeChat replacement flow


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

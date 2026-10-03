# R53A Staging Identity Provider Contract

## Decision and scope

`SELECTED_IDENTITY_MODEL=OIDC_PROVIDER_NEUTRAL_DENY_BY_DEFAULT`

ARMS staging will accept short-lived signed identity tokens from one explicitly
configured OpenID Connect issuer through a provider-neutral verifier. The
verifier constructs the existing Phase 4 user or service transport principal
only after cryptographic and claim validation succeeds. Authentication alone
never grants an action, account, trading, deployment, or production authority.

No external identity-provider tenant, application, user, service principal,
key, redirect URI, domain, or paid resource is created by this milestone.

## Trust configuration

| Field | Staging requirement |
| --- | --- |
| Issuer | One exact, normalized HTTPS issuer identifier selected during external staging provisioning. Subdomains, aliases, HTTP, wildcard, prefix, and case-folded matches are denied. |
| Audience | Exact value `arms-ai-staging-api`. A token must contain it as its sole audience or as one exact member of a bounded audience array. |
| Discovery | Fetch only from the configured issuer's OIDC discovery location through approved outbound policy. Redirects to another origin are denied. |
| Key set | Signed keys come from the discovery document's same-origin `jwks_uri`; each accepted key has a unique nonempty `kid`. |
| Algorithms | External staging allowlist is `RS256` or `ES256` with provider keys of approved strength. `none`, symmetric HMAC, algorithm substitution, and token-selected algorithms are denied. |
| Clock | Validation uses a trusted UTC clock. Maximum allowed clock skew is 60 seconds and never extends maximum token lifetime. |
| User token lifetime | At most 10 minutes from `iat` to `exp`. |
| Service token lifetime | At most 5 minutes from `iat` to `exp`. |
| Key cache | Bounded to 15 minutes and invalidated immediately on unknown `kid`, signature failure, issuer configuration change, or explicit revocation signal. |

R53B may use a local test issuer and synthetic HMAC key to exercise JWT parsing,
claims, signature failure, and rotation without dependencies. That algorithm and
key are marked `LOCAL_TEST_ONLY` and provide no evidence for external staging's
asymmetric-key or discovery behavior.

## Required token envelope

The compact JWT must have exactly three nonempty base64url segments and a
protected header containing only allowlisted fields. Duplicate JSON keys,
non-UTF8 text, invalid base64url, excess size, excessive nesting, and noncanonical
claim types are rejected before principal construction.

Required protected header fields:

- `alg`: one configured allowlisted algorithm;
- `kid`: exact key identifier from the active issuer key set;
- `typ`: exactly `JWT` or the provider's reviewed access-token type.

Required claims for every principal:

| Claim | Contract |
| --- | --- |
| `iss` | Exact configured issuer. |
| `aud` | Contains exact configured audience. |
| `sub` | Stable opaque provider subject; display name or email is not identity. |
| `iat` | Integer NumericDate, no more than 60 seconds in the future. |
| `nbf` | Integer NumericDate; token is denied before this instant after bounded skew. |
| `exp` | Integer NumericDate strictly after `iat`; token is denied at expiry. |
| `jti` | Nonempty bounded unique token identifier for replay/audit correlation. |
| `principal_type` | Exactly `user` or `service`. |
| `tenant_id` | One validated tenant identifier; wildcard and multi-tenant inference are denied. |
| `roles` | Nonempty bounded array of unique allowlisted role identifiers. |
| `account_ids` | Bounded array of unique account IDs within `tenant_id`; empty means no account scope. |

Unknown claims do not create authority. Claims used for authorization have exact
case-sensitive names and types. A token is rejected when a required claim is
missing, duplicated, null, malformed, internally inconsistent, or outside the
configured bounds.

## User identities

1. A user token uses `principal_type=user` and maps `(issuer, sub)` to exactly
   one active ARMS user record with an immutable tenant association.
2. The token's `tenant_id` must equal the canonical user's tenant. A token cannot
   select or switch tenant context through a request parameter or header.
3. Provider group or role claims map through a committed allowlist to existing
   ARMS roles and permissions. Unknown roles grant nothing; an unmapped or
   contradictory role set is denied.
4. Token `account_ids` are intersected with the canonical server-side account
   scope. The effective scope cannot exceed either source. Unknown, foreign, or
   cross-tenant accounts are denied.
5. Disabled, suspended, deleted, or unknown users are denied even when signature
   and claims are valid.
6. Email, display name, username, group label, and tenant name are display or
   lookup metadata only and never replace the stable subject and canonical
   authorization record.

## Service identities

1. A service token uses `principal_type=service`; `(issuer, sub)` maps to one
   existing immutable `ServiceIdentity`.
2. The canonical service identity controls tenant scope, account scope, and
   `ServicePermission`. Token claims can narrow those sets but cannot expand
   them.
3. API, worker, scheduler, migration, backup, restore, telemetry, and identity
   verification use separate subjects. Shared all-purpose service tokens are
   prohibited.
4. Workload identity or client credentials used to obtain a service token are
   managed through the R52A secret boundary and never appear in the access token,
   logs, configuration, or ARMS durable state.
5. No service role contains broker, order, portfolio mutation, PAPER, LIVE, or
   production mutation permission.

## Authorization composition

After token validation, the adapter constructs an authenticated transport
principal with the canonical tenant and account scope. The existing Phase 4
authorization boundary then evaluates the requested action independently.

- Missing or invalid authentication produces no principal.
- A valid token with insufficient role, service permission, tenant, or account
  scope receives a denial decision.
- The request tenant and account must match the authenticated principal and a
  known canonical account.
- Role names are mapped to fixed permissions; clients cannot submit permissions.
- Read endpoints remain read-only and cannot create an order, PAPER/LIVE
  position, protection/OCO, portfolio/account mutation, execution record, or
  execution event.
- Identity validation has `execution_authorized=false`,
  `production_mutation_authorized=false`, and `live_trading_authorized=false`.

## Token validation order

The verifier performs these checks in order and stops at the first denial:

1. enforce transport size and compact JWT shape;
2. strictly decode header and claims with duplicate-key rejection;
3. enforce header type, algorithm allowlist, and `kid` shape;
4. find the key only in the configured issuer's bounded active key set;
5. verify the signature over the original encoded header and payload;
6. verify exact issuer and audience;
7. verify `iat`, `nbf`, `exp`, maximum lifetime, and bounded clock skew;
8. validate `jti`, principal type, tenant, roles, and account claim shapes;
9. resolve the canonical user or service identity;
10. intersect canonical roles, permissions, tenant, and account scope;
11. construct the principal with no execution authority;
12. evaluate the requested transport action and replay policy separately.

No failed step triggers a fallback issuer, unsigned parsing mode, stale unknown
key, request-provided key, previous tenant, default role, or public endpoint.

## Key rotation and outage behavior

- A new signing key has a new `kid` and overlaps with the previous verified key
  only for a configured bounded interval no longer than the maximum token
  lifetime plus clock skew.
- Unknown `kid` triggers one bounded refresh from the configured issuer. If it
  remains unknown, validation fails. It never tries every key or trusts token
  header URLs such as `jku` or `x5u`.
- Removed or revoked keys are rejected immediately after authoritative refresh.
  Cached keys cannot extend their approved retirement time.
- Tokens signed by both current and explicitly overlapping keys are tested during
  rotation. After overlap, the retired key is denied.
- Discovery/JWKS outage may use a still-fresh previously validated cache until
  its fixed expiry. When the cache is missing, stale, inconsistent, or revoked,
  readiness and authentication fail closed.
- Key material, raw tokens, discovery responses, and native provider errors are
  never logged or persisted in ARMS audit records.

## Audit, privacy, and replay

Successful and denied attempts record a correlation ID, sanitized outcome code,
issuer identifier, key ID, principal type, canonical principal ID when resolved,
tenant ID, requested account ID, action, and UTC time. Raw JWTs, signatures,
claims documents, user profile data, keys, client credentials, and provider error
text are prohibited.

The bounded request ID and nonce replay controls remain separate from JWT `jti`.
Neither a new token nor a rotated signing key permits replay of a previously
accepted state-changing request. Read-only status and health checks do not cause
token issuance, secret resolution, account mutation, or trading effects.

## R53B acceptance criteria

Using only local test issuer keys and synthetic identities, verify:

1. a valid token becomes the expected no-execution transport principal;
2. expired, not-yet-valid, excessive-lifetime, wrong-audience, wrong-issuer,
   missing-claim, malformed, and signature-failed tokens produce no principal;
3. tenant and account mismatches are denied before source invocation;
4. unknown roles and role escalation cannot add a permission;
5. current and overlapping rotated keys validate, while an unknown or retired
   key fails;
6. user and service claims map to their distinct canonical models;
7. every rejection has zero broker calls, orders, positions, protections/OCO,
   portfolio/account mutation, fill-like records, and execution events.

## R53A status

`STAGING_IDENTITY_CONTRACT_DEFINED=TRUE`

`REAL_IDENTITY_PROVIDER_TENANT_CREATED=FALSE`

`REAL_ISSUER_KEYS_USED=FALSE`

`PRODUCTION_MUTATION_AUTHORIZED=FALSE`

`LIVE_AUTHORITY=FALSE`

# R52A Staging Secret Contract

## Decision and scope

`SELECTED_SECRET_MODEL=PROVIDER_NEUTRAL_REFERENCE_AND_METADATA`

ARMS components receive opaque secret references and non-sensitive lifecycle
metadata through a provider-neutral interface. Only the selected provider
adapter may resolve a reference to short-lived in-memory material. This document
does not select a commercial provider, create an external secret, accept a real
credential, or authorize deployment or trading.

The Phase 4 `SecretReference`, `SecretProvider`, `SecretMaterial`, redaction, and
service-identity contracts are the foundation. Phase 5 staging adds explicit
environment scope, purpose, version, rotation, expiry, identity binding, and
audit requirements around that boundary.

## Non-secret reference model

Every required secret has an immutable descriptor containing only:

| Field | Requirement |
| --- | --- |
| `reference_id` | Opaque validated identifier such as `secrets/arms/staging/postgres`; never a URI, DSN, token, password, key, or encoded value. |
| `environment` | Exactly `staging` for this phase. A development, test, production, or wildcard descriptor is rejected. |
| `purpose` | One allowlisted use such as database connection, identity verification, backup encryption, or alert delivery. |
| `version` | Provider-neutral immutable version label or positive rotation sequence. `latest` and other moving aliases are prohibited at activation time. |
| `issued_at` | Canonical timezone-aware UTC timestamp for the active version. |
| `rotate_after` | Canonical UTC timestamp after `issued_at`; reaching it makes rotation due and produces a health warning. |
| `expires_at` | Canonical UTC timestamp after `rotate_after`; resolution and use are denied at or after this instant. |
| `previous_reference_id` | Required for sequence greater than one and distinct from the current reference; retained only for the bounded overlap/revocation workflow. |
| `service_id` | Exact authenticated service identity allowed to request the secret. |
| `tenant_scope` | Explicit immutable tenant set where the secret is tenant-specific; an empty value means service-level scope, never all tenants by inference. |

Descriptors may be stored in configuration, manifests, and audit records because
they contain no secret material. Their schema is allowlisted: provider response
objects, arbitrary annotations, exception text, and secret-derived hashes are
not persisted as metadata.

## Provider-neutral interface

The staging adapter must support these conceptual operations without exposing a
provider SDK to application code:

1. `describe(reference, principal, now)` returns validated non-secret metadata.
2. `resolve(reference, principal, now)` returns an ephemeral `SecretMaterial`
   only when the descriptor is active and the identity, environment, purpose,
   tenant scope, and permission all match.
3. `refresh(reference, principal, now)` obtains the currently approved immutable
   version after rotation. It cannot follow an unapproved moving alias.
4. `close(material)` zeroizes the mutable local buffer immediately after use.
5. `health()` reports only provider availability, metadata freshness, rotation
   due, and expiry status using fixed sanitized codes.

Every operation fails closed. Missing, unavailable, malformed, wrong-environment,
wrong-purpose, unauthorized, expired, revoked, or ambiguous data yields no
material. A provider outage cannot fall back to environment variables, local
files, embedded defaults, a previous secret, or another provider unless an
explicitly reviewed rotation policy identifies that exact previous version and
its bounded overlap window is still active.

## Environment and service identity scope

- The configured runtime environment and descriptor environment must both equal
  `staging`. Environment names are compared as validated identifiers.
- The caller presents an authenticated service identity before provider access.
  A string service name alone is insufficient.
- The identity must be active, cover the requested tenant where applicable, and
  hold the single permission associated with the descriptor purpose.
- API, migration, worker, scheduler, backup, restore, telemetry, and identity
  verification services use distinct identities and secret references.
- A worker cannot resolve API, migration, backup, identity-signing, or alert
  credentials. A read-only service cannot resolve write credentials.
- No service permission grants broker, order, portfolio mutation, PAPER, LIVE,
  or production authority. Secret resolution never changes those authority bits.
- Cross-tenant resolution is denied before calling the provider adapter.

## Rotation and expiry

1. Rotation creates a new immutable reference/version and increments the
   sequence. It never replaces material behind an already activated identifier.
2. `issued_at < rotate_after < expires_at` is mandatory. Naive or non-UTC
   timestamps are rejected at the contract boundary.
3. Before `issued_at`, the version is inactive. From `rotate_after` until
   `expires_at`, it remains usable only during the configured bounded overlap
   while health reports rotation due. At `expires_at`, use is denied.
4. Activation validates the new material without logging it, switches new
   acquisitions atomically, and retains the old version only for the approved
   overlap. Existing material is closed after its operation completes.
5. Revocation ends use immediately regardless of the scheduled expiry. Provider
   caches must honor the configured revocation and maximum cache age.
6. Failed rotation leaves the current unexpired version active only until its
   original expiry. It cannot extend expiry, silently revert, or convert an
   unavailable component into healthy state.
7. A rotation event records reference IDs, versions, service identity, UTC
   timestamps, outcome code, and correlation ID. It never records values or
   secret-derived fingerprints.

## Material handling and persistence prohibition

- Secret values exist only in bounded mutable memory for the shortest operation
  that requires them and are zeroized on close, exception, cancellation, and
  shutdown where the runtime permits.
- Values must not enter Git, source, configuration, command arguments, process
  titles, environment snapshots, database rows, durable state, backup manifests,
  build artifacts, caches on disk, logs, traces, metrics, alerts, audit fields,
  HTTP responses, exception messages, test reports, or decision records.
- Application objects expose redacted `str` and `repr` forms. Serialization,
  copying, equality diagnostics, and arbitrary object inspection of material are
  prohibited.
- Reference IDs are safe metadata only after validation. They must not include
  usernames, hosts, account numbers, tokens, or connection strings.
- Provider errors are translated to fixed error types and detail codes before
  crossing the adapter boundary. Native error text is never retained.
- Debug mode does not weaken redaction or persistence rules.

## Minimum staging secret inventory

| Purpose | Owning identity | Consumers | Required before external staging |
| --- | --- | --- | --- |
| PostgreSQL runtime connection | API database identity | API replicas | Yes |
| PostgreSQL migration connection | Migration identity | One migration job | Yes |
| Worker storage/transport | Worker identity | Worker replicas | Yes when that transport is enabled |
| Scheduler storage | Scheduler identity | Scheduler replicas | Yes |
| Identity verification keys/config | Auth verifier identity | API/auth replicas | Yes |
| Backup encryption | Backup identity | Backup and isolated restore jobs | Yes |
| Alert delivery | Alert identity | Alert dispatcher only | Yes when external alerting is enabled |

Identity signing keys, broker credentials, LIVE account credentials, production
database credentials, and real notification tokens are outside Phase 5 local
scope and must not be introduced for rehearsal.

## Configuration and deployment rules

1. Committed configuration contains descriptors and provider-neutral endpoint or
   workload-identity references only. It contains no material or reusable test
   password.
2. The selected external provider adapter and workload identity require a later
   explicit approval and staging-only configuration. The existing Phase 4
   environment provider remains an implementation seam; it is not external
   staging approval evidence.
3. Startup resolves all secrets classified as required for that process. A
   required failure keeps the component unready and prevents its state-changing
   work. Optional disabled features do not trigger secret resolution.
4. Read-only health, status, dashboard, metrics, and subscription operations do
   not resolve secret material merely to render a response.
5. Build and package steps validate references and descriptor schemas but never
   contact the provider or embed resolved values.
6. A process receives only the descriptors for its own identity and purpose.
   Full-environment secret inventories are prohibited.

## Audit and observability

Allowed audit fields are event type, provider ID, validated reference ID,
version, environment, purpose, requesting service ID, tenant ID when applicable,
UTC time, correlation ID, sanitized outcome, rotation-due flag, and expiry time.

Metrics use bounded labels and may count successful, denied, missing, expired,
revoked, invalid, and unavailable outcomes. Reference IDs, service IDs, tenant
IDs, exception messages, and material are not metric labels. Logs and alerts pass
through the centralized redactor, including provider and worker failure paths.

## R52B acceptance criteria

The local provider rehearsal must use synthetic values only and prove:

1. load by opaque reference and exact identity/environment/purpose scope;
2. successful immutable-version rotation and bounded previous-version overlap;
3. missing, malformed, unavailable, expired, revoked, and unauthorized requests
   fail before a consumer receives material;
4. material closes and zeroizes after success and every injected failure;
5. values do not appear in public configuration, persisted files, exceptions,
   logs, audit, metrics, alerts, `str`, or `repr`;
6. worker identities cannot access secrets assigned to other roles or tenants;
7. provider or rotation failure creates no broker call, order, position,
   protection/OCO, portfolio/account mutation, fill-like record, or execution
   event.

## R52A status

`STAGING_SECRET_CONTRACT_DEFINED=TRUE`

`REAL_SECRET_VALUES_USED=FALSE`

`EXTERNAL_SECRET_PROVIDER_SELECTED=FALSE`

`EXTERNAL_SECRET_PROVIDER_PROVISIONED=FALSE`

`PRODUCTION_MUTATION_AUTHORIZED=FALSE`

`LIVE_AUTHORITY=FALSE`

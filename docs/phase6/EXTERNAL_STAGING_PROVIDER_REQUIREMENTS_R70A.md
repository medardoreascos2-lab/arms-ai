# Phase 6 external staging provider requirements (R70A)

## Scope and authority boundary

Phase 6 prepares a real external staging environment without creating it. These
requirements cover provider selection, infrastructure templates, deployment
manifests, and later operator validation. They authorize no resource creation,
credential use, DNS change, artifact upload, broker connection, PAPER or LIVE
position, production mutation, or financial execution.

All staging data must be synthetic or explicitly approved non-sensitive test
data. Instrument-aware fixtures and configuration must support both NQ and MNQ,
preserve their distinct point values and sizing, and label any aggregation.

## Cross-cutting requirements

Every selected provider and component must:

1. expose a documented infrastructure API suitable for reviewable IaC;
2. support least-privilege service identities and auditable access;
3. encrypt transport with current TLS and data at rest with managed or
   customer-controlled keys where required;
4. keep the database and internal services off the public internet;
5. support immutable deployment identity, environment separation, bounded
   resources, health checks, and deterministic rollback;
6. emit logs and metrics without secret values, credentials, account numbers,
   raw tokens, or uncontrolled tenant labels;
7. fail closed when identity, secrets, risk data, database state, or required
   health evidence is missing, stale, invalid, or inconsistent;
8. preserve the invariant that denied or rejected work creates no execution,
   portfolio, account, position, protection/OCO, fill-like journal, or external
   delivery effect;
9. expose no broker, PAPER, LIVE, production, or financial-execution authority;
10. support deletion and cost shutdown without destructive database rollback.

## Cost classification

- `LOW`: normally one small staging resource or usage-based service with a
  practical idle floor.
- `MEDIUM`: continuously running managed service, redundant component, or
  material storage/telemetry retention.
- `HIGH`: multi-zone capacity, dedicated tenancy, large retention, high-volume
  telemetry, or premium security/availability features.

Exact prices belong to a later operator estimate using the selected provider,
region, account discounts, taxes, and current public calculator. Phase 6 does
not invent a currency amount.

## Requirements matrix

| Category | Minimum capability | Security requirements | Cost sensitivity | Portability | Backup requirements | HA needs | Required staging tests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PostgreSQL | Supported PostgreSQL major version, UTF-8, UTC sessions, exact `NUMERIC` behavior, bounded pool, transactions, forward-only migrations, health/read-only modes, tenant predicates | Private endpoint, TLS verification, encryption at rest, separate app/migration/backup identities, no public superuser, audited privileged access | `MEDIUM`; instance class, storage, IOPS, replicas, backup retention, egress | Standard SQL and provider-neutral adapter; provider features isolated behind configuration | Database-consistent encrypted backups, PITR where supported, retention, restore to a new target | Staging may begin single-primary; failover behavior and recovery limits must be explicit before readiness | Migration, exact decimal/timestamp round trip, concurrent writes, isolation, pool exhaustion, abort, failover, backup/restore, tenant separation |
| Secret manager | Versioned secret references, scoped retrieval, rotation metadata, availability status | Workload identity, least privilege per service/purpose/environment, encryption, audit, revocation; values never enter IaC state, Git, logs, metrics, manifests, or health payloads | `LOW` to `MEDIUM`; secret versions, API calls, rotation functions, private endpoints | Application uses existing provider-neutral secret interface and opaque references | Provider durability plus documented recovery/export policy for metadata; no plaintext backup | Multi-zone managed durability preferred; outage must stop dependent startup or work safely | Missing/expired/wrong-scope denial, rotation overlap and retirement, outage, audit, recursive leak scan |
| Identity provider | OIDC issuer, fixed audience, signed JWT, JWKS, users and service identities, tenant/account/role claims | Asymmetric algorithms, key allowlist, short lifetime, revocation/lifecycle policy, MFA for operators, audit, replay controls | `LOW` to `MEDIUM`; active users, service identities, premium policy/log retention | Standards-based OIDC/JWT; claim mapping isolated from provider API | Configuration and mapping recovery documented; signing private keys never exported into application backups | Issuer/JWKS availability expectations and cached-key limits explicit | Issuer/audience/signature/lifetime/claim validation, rotation, retired key, replay, cross-tenant denial, unavailable JWKS |
| Telemetry | Metrics, structured logs, bounded labels, dashboards, health and SLO queries | TLS, workload identity, retention/access policies, tenant-safe redaction, append integrity where available | `MEDIUM` to `HIGH`; ingestion volume, cardinality, retention, query and egress | Open formats and provider-neutral metric/event contracts preferred | Dashboard/alert definitions versioned in Git; provider data retention documented | Required telemetry failure must degrade health without enabling unsafe work | Export, redaction, label bounds, dropped-record accounting, retention, query, collector outage, dashboard/SLO checks |
| Alert delivery | Severity, dedupe, recovery, routing, acknowledgement and escalation | Dedicated narrow identity, sanitized payloads, destination allowlist, audit, rate limits | `LOW` to `MEDIUM`; incident users, messages, integrations | Alert policy remains provider neutral; destination adapter isolated | Routing and escalation configuration reproducible; no credential values in backup | At least two operator routes before production consideration; staging may use one approved route plus local fallback | Trigger, dedupe, recovery, delivery failure, retry bounds, secret redaction, unauthorized destination denial |
| Object storage and backups | Versioned encrypted objects, checksums, lifecycle/retention, separate restore access | Private access, TLS, managed keys, least privilege, deny public access, immutability where available, access audit | `LOW` to `MEDIUM`; retained bytes, versions, requests, retrieval and egress | Standard archive format and manifest independent of object provider | Off-host database/audit/research provenance, RPO/RTO, retention locks, isolated restore | Provider durability documented; cross-region copy deferred unless justified by risk/cost | Upload/download integrity, wrong key, corruption, retention, access denial, isolated timed restore and reconciliation |
| Artifact registry | Digest-addressed images/packages, immutable release references, scan metadata, retention | Workload identity, private repository, push/pull separation, signature/attestation verification, audit | `LOW` to `MEDIUM`; storage, scanning, transfer, retention | OCI-compatible artifacts and portable provenance/SBOM formats | Manifest, SBOM, provenance and signatures retained with artifact | Regional managed durability sufficient for staging; replicated registry optional | Build reproducibility, digest pinning, vulnerability/secret/config scan, signature policy, tamper and unauthorized push/pull denial |
| Container/runtime | Separate API, migration, worker, scheduler and research roles; health/readiness, limits, graceful termination | Non-root, read-only root where practical, dropped capabilities, immutable image digest, isolated service accounts, no host socket | `MEDIUM` to `HIGH`; CPU/memory reservations, replicas, load balancers, control plane | OCI images and declarative manifests; avoid provider-only runtime assumptions in application | Runtime definitions versioned; durable data remains in managed services | Two API replicas supported; worker/scheduler fencing; research cannot consume operational reserve | Startup, probes, signals, drain, restart, replica contention, resource pressure, rollout and rollback |
| Networking | Public ingress only at explicit API boundary; private DB/internal services; controlled service paths and egress | Default deny, security groups/firewall, private endpoints where justified, no broker destinations, flow/audit logs | `LOW` to `MEDIUM`; gateways, private endpoints, load balancer, egress and logs | Explicit network contract; provider-specific resources confined to IaC | Network configuration and flow-log policy versioned; no stateful data backup role | At least two availability-zone subnets where selected topology supports them; single-zone exceptions explicit | No public DB, ingress allowlist, service reachability, denied lateral path, denied broker path, bounded egress, partition response |
| TLS | Managed or approved certificates, TLS 1.2 minimum with TLS 1.3 preferred, verified service endpoints | Automated renewal, modern ciphers, hostname verification, private key isolation, no plaintext fallback | `LOW`; certificate and edge service costs, private CA may increase cost | Standard X.509 endpoints and provider-neutral client verification | Certificate configuration recoverable; private keys remain in managed boundary | Renewal and expiration monitoring required | Protocol/cipher scan, hostname and chain validation, expired/revoked certificate failure, renewal rehearsal |
| DNS | Dedicated staging names, low-risk records, explicit ownership and TTL | Restricted change role, change audit, no wildcard that broadens trust, certificate binding | `LOW`; hosted zone and query volume | Names and records represented as variables; no hard dependency in application logic | Zone/record definitions versioned without provider credentials | Provider DNS SLA documented; multi-provider DNS deferred | Dry-run record render, ownership validation plan, wrong-target detection, rollback plan; actual mutation requires approval |
| Multi-host orchestration | Replica placement, rolling updates, service discovery, job execution, persistent identity and fencing | Namespace/environment isolation, least-privilege workload identities, admission policy, secrets by reference, network policy | `HIGH`; control plane, redundant nodes, autoscaling floor | Declarative workloads and OCI artifacts; application leases remain provider neutral | State externalized; manifests and recovery order versioned | API replicas, worker takeover, scheduler single-owner, zone-aware placement where available | Multi-node load, worker/scheduler takeover, node loss, network partition, rollout, rollback, capacity and tenant fairness |

## Required role separation

The future staging environment must use distinct identities for API, database
migration, operational workers, research workers, scheduler leadership,
telemetry export, backup, isolated restore, artifact publication/runtime pull,
and operator read-only inspection. No role may receive broker credentials or
order authority. Migration, backup, restore, signing, and infrastructure
administration cannot be inherited by the application runtime.

## Required NQ and MNQ evidence

Provider and deployment validation must preserve distinct canonical instrument
identities, exact tick and point-value semantics, instrument-aware sizing,
separate research reports, explicitly labeled aggregation, and synthetic
normal, high/low volatility, gap, spread, stale-quote, and invalid-L1 cases for
both NQ and MNQ.

## Provider acceptance gates

A candidate can be recommended only when every category has a supported path,
the expected cost category is disclosed, the design can be destroyed without
data ambiguity, and all required tests can run without financial execution
authority. Missing security, identity, backup, or database evidence keeps the
provisioning gate at `HOLD` or `BLOCKED`.

## R70A status

`PROVIDER_REQUIREMENTS_DEFINED=TRUE`

`EXTERNAL_RESOURCES_CREATED=FALSE`

`COST_INCURRED=FALSE`

`CREDENTIALS_REQUIRED=FALSE`

`BROKER_AUTHORITY=FALSE`

`PAPER_AUTHORITY=FALSE`

`LIVE_AUTHORITY=FALSE`

`PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE`

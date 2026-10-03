# Phase 5 staging threat model (R61B)

## Scope and authority

This model covers the isolated local Phase 5 staging architecture and its
provider-neutral contracts. It excludes production deployment, real credentials,
external financial authority, broker connectivity, PAPER execution, and LIVE
execution. A successful local control remains staging evidence only.

## Assets

- tenant and account identities, scopes, and authorization decisions
- persisted snapshots, evaluations, portfolio views, journals, and outbox state
- audit chains and research provenance
- signing, service credential, and backup key references
- encrypted backup archives and restored database copies
- build manifests, source packages, scan reports, and release evidence
- worker leases, scheduler leadership, queues, metrics, alerts, and health state

## Trust boundaries

1. **Client to API:** untrusted request data crosses authentication,
   authorization, replay, tenant, account, and payload validation.
2. **API to durable state:** authorized scope crosses into tenant-keyed database
   operations and transactional outbox writes.
3. **Worker and scheduler to durable state:** service identity and lease ownership
   cross into durable job, outbox, and scheduling effects.
4. **Research to operational capacity:** untrusted workload size crosses resource
   quotas and the reserved operational capacity boundary.
5. **Runtime to secret provider:** code receives opaque secret references; local
   tests receive synthetic or ephemeral material only.
6. **Database to backup and restore:** state crosses authenticated encryption,
   schema, hash, tenant, audit, provenance, path, and freshness validation.
7. **Source to artifact:** allowlisted files cross reproducible build, manifest,
   static scan, reconstruction, and hash verification.
8. **Local staging to external providers:** no trust is granted. Identity, secret,
   database, telemetry, backup, DNS, and network controls remain blocked pending
   explicit provisioning and independent validation.

## Threat actors

- unauthenticated or incorrectly authenticated API clients
- authenticated users attempting tenant or account scope escalation
- compromised or stale service credentials
- replaying clients and concurrent duplicate request senders
- compromised workers or schedulers holding stale leases
- malicious or malformed backup, audit, research, or artifact inputs
- operators making an unsafe restore, rollback, configuration, or release choice
- dependency or build-system compromise
- excessive research consumers starving operational work
- an attacker with database or backup archive access

## Threats, controls, and residual risk

| Threat | Local staging controls and evidence | Residual risk or required external control |
| --- | --- | --- |
| Credential theft | Short synthetic token lifetimes, exact claims, key overlap and retirement tests, opaque secret references, redacted key objects, and no committed real secrets. | External IdP revocation, managed KMS rotation, access logging, workload identity, and emergency credential response remain unverified. |
| Tenant breakout | Canonical tenant claims, explicit account scopes, deny-by-default transport authorization, tenant-keyed durable state, scoped replay reservations, load isolation checks, and restore audit tenant binding. | Cloud database row security, network segmentation, and provider IAM need external staging validation. |
| Database compromise | Parameterized tenant data access, integrity checks, foreign keys, audit chains, encrypted backups, immutable source checks, and isolated restore roots. | Managed PostgreSQL access control, TLS, encryption at rest, privileged access monitoring, and point-in-time recovery are external blockers. |
| Worker compromise | Narrow service permissions, tenant/account preservation, expiring leases, stale-token rejection, bounded retries, dead letters, and no external delivery authority. | Host isolation, image admission, workload identity, and provider incident containment remain unverified. |
| Scheduler compromise | Single-owner leases, generations, expiry, safe takeover, and isolation between operational, outbox, and research work. | Distributed clock behavior and managed runtime failure domains require external staging. |
| Backup theft | Authenticated local-test encryption, ephemeral redacted keys, archive authentication, freshness checks, hash manifests, and isolated destinations. | Local cipher is not production encryption; managed KMS, object-store IAM, retention locks, and access alerts are required. |
| Supply chain compromise | Allowlisted reproducible packages, manifest hashes, secret/config/import scanning, symlink rejection, offline reconstruction, and read-only reconstructed files. | Signed provenance, dependency attestation, registry policy, and independent vulnerability services require external systems. |
| Research abuse | Separate research domain, bounded queues and workers, memory/disk budgets, throttling, and reserved operational capacity. | Host and cluster quotas must be mapped and load tested after external provisioning. |
| Replay and duplicate effects | Timestamp windows, nonces, request IDs, payload-bound idempotency, scoped reservations, transactional outbox, and multi-replica concurrency tests. | The local replay store is process-local in some rehearsals; an external shared implementation must be validated before multi-host use. |
| Audit tampering | Canonical hash chaining, exact sequence and tip, duplicate-field rejection, exact tenant coverage, and encrypted payload authentication. | External append-only retention and independent audit export are not provisioned. |
| Path traversal or overwrite | Absolute paths, resolved containment beneath an explicit isolated root, symlink rejection, exclusive file creation, and existing-destination refusal. | Operating-system ACLs and storage mount policy remain environment responsibilities. |
| Unsafe deserialization | Bounded canonical JSON, exact field sets, duplicate-field rejection, strict base64, no executable serialization, and no pickle. | Future formats require a fresh review before admission. |
| Secret leakage | Static artifact checks, sensitive filename rejection, redacted representations, generic cryptographic errors, and synthetic fixtures. | Provider logs and secret-manager audit trails require external staging. |

## Abuse paths and safe outcomes

- Invalid authentication, tenant scope, account scope, replay state, input shape,
  backup authentication, audit integrity, or artifact integrity fails closed.
- A denied request produces no broker call, PAPER/LIVE position, portfolio change,
  protection order, outbox effect, or execution record.
- A stale worker or scheduler cannot retain ownership after lease expiry or a new
  generation takes over.
- A restore cannot overwrite the active database or an existing destination and
  cannot escape its explicit isolated root.
- Resource pressure throttles research while preserving reserved operational
  capacity; hard limits block additional work.
- Recovery and release remain blocked until explicit operator action. Local test
  success cannot grant production, broker, or execution authority.

## Residual risk disposition

Phase 5 remains `HOLD`. The verified controls support continued local composition
and rehearsal. External identity, secret, PostgreSQL, network, telemetry, backup,
artifact-signing, and runtime isolation controls must be provisioned explicitly
and validated before the release gate can return
`READY_FOR_EXTERNAL_STAGING_PROVISIONING`. That state still cannot mean
`READY_FOR_PRODUCTION`.

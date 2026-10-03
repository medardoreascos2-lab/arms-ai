# R50B Phase 5 Staging Topology Candidates

## Decision scope

This comparison identifies a topology that Phase 5 can validate without paid
provisioning, real credentials, production deployment, broker connectivity, or
LIVE authority. Provider cost is not estimated because no provider, region,
service tier, retention period, traffic profile, or organizational discount has
been approved.

## Candidate A: isolated local process topology

Run API replicas, workers, schedulers, metrics, alert receiver, secret and
identity test issuers, backup tooling, and research jobs as isolated local
processes or in-process replicas. Use temporary directories and loopback-only
interfaces. Use the Phase 3 SQLite store for executable local integration and
validate the Phase 4 PostgreSQL adapter statically while PostgreSQL remains
unavailable.

This candidate is available on the current host and exercises application
contracts, ownership, authorization, isolation, encryption format, deterministic
packaging, load behavior, failure ordering, and release gates. It cannot prove
PostgreSQL server behavior, container boundaries, external identity, managed
secret access, external telemetry, or cloud failure domains.

## Candidate B: isolated local container topology

Run separate API, PostgreSQL, migration, worker, scheduler, metrics receiver,
alert receiver, and backup containers on an isolated local network. Use
ephemeral volumes and synthetic credentials. Bind only explicitly required
loopback ports and deny broker or arbitrary outbound destinations.

This candidate provides stronger process, network, PostgreSQL, volume, restart,
and multi-replica evidence without paid infrastructure. Docker and Podman are
currently unavailable, so Phase 5 cannot execute this candidate on this host.
Its compose and provider-neutral contracts may still be prepared and statically
validated without claiming a container rehearsal.

## Candidate C: provider-managed cloud-equivalent staging

Use a managed PostgreSQL service, workload identities, managed secrets,
external telemetry, encrypted object storage, artifact registry, private
networking, and separately scaled API, worker, and scheduler services. No
broker routes or financial execution authority are included.

This candidate can provide the closest evidence for external failure domains,
managed backups, identity rotation, telemetry delivery, artifact provenance,
and horizontal scaling. It requires provider selection, credentials, account
access, cost approval, and infrastructure provisioning, so it is outside the
autonomous Phase 5 execution boundary.

## Comparison

| Dimension | Candidate A: local processes | Candidate B: local containers | Candidate C: managed cloud equivalent |
| --- | --- | --- | --- |
| Security | Loopback, temporary paths, synthetic identity, no external authority; process isolation is host-level only. | Explicit container/network/volume boundaries with synthetic identities; runtime hardening can be exercised. | Provider IAM, private networking, managed encryption, and external audit can be exercised after approval. |
| Cost | Uses already-available local resources; no provisioning action. | Uses local resources but requires an already-installed container runtime. | Cost is unknown until provider, region, size, retention, and traffic are approved. |
| Complexity | Lowest operational complexity; deterministic Python and filesystem tooling. | Moderate orchestration, image, network, health, and volume complexity. | Highest integration and governance complexity across multiple managed services. |
| Portability | High for provider-neutral application contracts; lower fidelity for PostgreSQL/container behavior. | High when images and compose contracts remain provider-neutral. | Lower portability where provider IAM, storage, telemetry, and networking semantics differ. |
| Backup | Encrypted local archive and isolated temporary restore can be proven. | Database-aware snapshot and isolated volume restore can be rehearsed locally. | Off-host retention, immutability, managed PITR, and key custody can be proven after provisioning. |
| Monitoring | Local metrics and fake alert receiver; no external delivery proof. | Collector and receiver containers can validate transport and restart behavior. | Real collector retention, dashboards, access controls, alert routing, and SLOs can be validated. |
| Failure isolation | Separate logical identities and processes; one host remains a common failure domain. | Separate containers and volumes; still one physical host. | Multiple service and potentially zone failure domains, subject to approved topology. |
| Testability | Available now; supports deterministic fake clocks, replicas, load, and failure injection. | Strong local integration when a container runtime is available. | Strongest operational realism but slower, cost-bearing, credentialed, and externally stateful. |
| PostgreSQL evidence | Static adapter/SQL contract only on this host. | Real ephemeral PostgreSQL if runtime becomes available. | Real managed PostgreSQL after explicit provisioning approval. |
| Secret and identity evidence | Synthetic local providers and issuer keys. | Synthetic services across network boundaries. | Real provider rotation, revocation, workload identity, and audit after approval. |
| Rollback evidence | Application compatibility and isolated file restore simulation. | Image/process rollback plus PostgreSQL restore into separate volumes. | Deployment-controller rollback and managed restore into separate infrastructure after approval. |

## Safety constraints shared by every candidate

1. No topology includes a broker endpoint, order authority, PAPER/LIVE position
   creation, or production mutation authority.
2. Authentication, tenant/account authorization, replay protection, audit, and
   fail-closed health remain mandatory.
3. A failed or unknown dependency keeps affected operations blocked.
4. Backups restore only into a separate destination until reconciliation and
   explicit operator release.
5. Research promotion stops at human review.
6. No provider credential or secret value is stored in source, Git, manifests,
   logs, errors, alerts, or reports.

## Evaluation

Candidate A is the only fully executable candidate on the current host.
Candidate B is the preferred higher-fidelity local target when an approved
container runtime is already available. Candidate C is the future external
staging mapping and requires a separate approval. R50C will select the Phase 5
execution topology and define how evidence from Candidate A maps, and does not
map, to Candidates B and C.

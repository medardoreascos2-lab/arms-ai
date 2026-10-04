# Phase 6 external staging threat review (R76A)

## Scope and status

This review covers the selected AWS external staging design, its Terraform
templates, workload manifests, local provider emulation, NQ/MNQ synthetic
research paths, and future operator provisioning boundary. It does not certify
an AWS account, network, identity tenant, artifact, or runtime because none has
been provisioned.

`THREAT_REVIEW_STATUS=PASS_WITH_OPERATOR_ACTIONS`

`EXTERNAL_RESOURCES_CREATED=FALSE`

`PROVISIONING_AUTHORIZED=FALSE`

## Threat register

| Threat | Assets and trust boundary | Attack / failure | Preventive controls in templates | Detection and response | Residual risk / gate |
| --- | --- | --- | --- | --- | --- |
| Internet ingress | Public TLS boundary, private API tasks, tenant requests | Scanning, exploit traffic, denial of service, bypass of intended ingress | Empty ingress allowlist by default; HTTPS-only design; API receives traffic only from the ingress security group; private task IPs; non-root read-only containers; dropped Linux capabilities | Load balancer/WAF/flow logs and API denial metrics after provisioning; isolate service and revoke ingress on anomaly | Exact CIDRs, certificate, rate limits, WAF policy and load test require operator evidence; HOLD until configured |
| Credential compromise | Human federation and workload IAM boundary | Stolen operator session or task credentials used across services | External OIDC; short workload sessions; dedicated roles; no static cloud credentials in source or manifests; separate deploy, migration, backup and restore duties | Cloud identity/IAM audit logs, auth-denial alarms, role revocation and session invalidation | Account controls, MFA, break-glass process and federation mappings require operator validation |
| Tenant breakout | OIDC claims, API authorization, PostgreSQL rows, research queues | A tenant reads or mutates another tenant's state | Required issuer/audience/tenant/role claims; tenant-scoped application rules; tenant and instrument scope required in queues; separate research storage and role | Authorization denial metrics, audit chain and cross-tenant negative tests | Row-level policy and application query behavior require deployed database integration evidence |
| Secret exfiltration | Secrets Manager, task environment, logs and IaC state | Plaintext values enter Git, state, logs, health output or broad IAM reads | IaC creates empty references only; secret values absent from variables/manifests; exact reader policies; KMS encryption; telemetry data protection; render accepts opaque references | Config security scan, log redaction findings, Secrets Manager and KMS audit | Secret insertion, rotation and leak scanning remain operator actions; any value exposure is BLOCKED |
| DB compromise | Private RDS, database identities, durable operational state | Public reachability, credential theft, SQL abuse, destructive admin access | Private subnets and security group references; `publicly_accessible=false`; TLS forced; storage/KMS encryption; IAM DB auth capability; deletion protection; exact decimal contract | RDS/PostgreSQL logs, connection alarms, immutable audit exports, isolated restore validation | Least-privilege SQL grants, migrations and live connectivity require plan and post-provision checks |
| Supply chain | Source, dependencies, build pipeline, OCI image, deployment manifest | Malicious dependency/build step or unsigned artifact reaches staging | No automatic build/upload; immutable registry tags; digest pinning; signature, provenance and scan gates; separated publisher/puller roles | SBOM, vulnerability/secret scan, provenance verification and registry audit before deployment | Build service and signing identity are not selected; deployment remains HOLD until evidence exists |
| Artifact tampering | ECR repository and image digest between publication and runtime | Mutable tag or replaced image is executed | ECR tag immutability, KMS encryption, digest-required manifests, signature/provenance requirements, bounded publisher role | Compare approved digest and signature at render and deployment; deny unknown digest; audit registry writes | No artifact has been built or uploaded; operator must verify digest and signer trust root |
| Backup theft | Encrypted RDS backups and off-host S3 objects | Public disclosure, unauthorized restore, copied or downgraded backup | S3 public access block, TLS-only bucket policy, KMS encryption, versioning, governance lock, separate write and restore-read policies | S3/KMS audit, checksum/manifest validation, access alert and isolated restore reconciliation | Key policy and operator restore access require account review; backup success never implies restore success |
| Identity forgery | External issuer, JWKS, token claims and application session | Forged token, issuer/audience confusion, stale or attacker-controlled JWKS | Exact issuer/audience/JWKS config, required claims, dedicated staging audience, no client secret in manifests; JWKS outage blocks protected service | Auth denial/alarm telemetry, issuer audit and key-rotation rehearsal; reject unknown/stale key | Tenant configuration, TLS validation, caching and rotation overlap require deployed issuer evidence |
| Worker takeover | Worker/scheduler/research task identities, queues and database | Compromised task mutates operational state, escalates laterally or duplicates work | Per-service roles; private subnets; constrained egress; read-only/non-root workload posture; durable outbox; leases and monotonic fencing; research queue/storage isolation; no broker/PAPER/LIVE authority | Heartbeats, lease-loss metrics, outbox failures, task replacement, role revocation and audit reconciliation | Runtime enforcement and compromised-host drill require external staging; all execution paths remain absent |

## Cross-cutting fail-closed rules

1. Missing database, secret, or identity evidence blocks readiness and new work.
2. Missing telemetry degrades health and pauses new work and research.
3. Missing backup or artifact registry evidence holds release/provisioning.
4. Any unresolved placeholder, plaintext secret, public database, open security
   group ingress, unrestricted workload egress, debug enablement, broker
   credential, LIVE flag, or production flag returns `BLOCKED`.
5. Read-only health, status, reporting and subscription operations have no
   execution side effects.
6. Rejected or blocked input never creates orders, positions, portfolio state,
   protections, OCO records, fills, or execution-equivalent journal entries.

## Required operator evidence before provisioning

- reviewed native Terraform/OpenTofu formatting, validation and exact plan;
- approved account, region, encrypted/locked state backend, budget and tags;
- identity tenant, MFA, role mappings, JWKS rotation and break-glass process;
- exact ingress CIDRs, TLS certificate, DNS name, WAF/rate-limit decision and
  constrained egress proof;
- SQL grants, secret insertion/rotation, KMS policies and audit destinations;
- signed digest-pinned artifact, SBOM, provenance and scan evidence;
- backup key/retention/access review plus isolated restore rehearsal plan; and
- incident ownership, alerts, response runbooks and evidence retention.

These actions require separate approval. This review grants no provider,
broker, PAPER, LIVE, production, financial execution, DNS, artifact upload, or
resource creation authority.

`BROKER_AUTHORITY=FALSE`

`PAPER_AUTHORITY=FALSE`

`LIVE_AUTHORITY=FALSE`

`PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE`

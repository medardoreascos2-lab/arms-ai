# Phase 6 operator provisioning plan (R77C)

## Purpose and current boundary

This is the exact future operator checklist for creating the isolated AWS
staging environment described by Phase 6. Every checkbox is intentionally
open. Phase 6 performed none of these external actions.

`CURRENT_STATUS=READY_FOR_OPERATOR_PROVISIONING`

`READY_FOR_PRODUCTION=FALSE`

`PLAN_EXECUTION_AUTHORIZED=FALSE`

`EXTERNAL_ACTIONS_PERFORMED=FALSE`

An operator must stop before the first external action until a separate change
record explicitly approves the account, region, credentials, budget, exact
plan, and named operators. Approval to inspect or plan does not authorize an
apply, artifact upload, DNS change, workload deployment, broker connection, or
trading action.

## External action classification

| Action | Creates external resources | Incurs cost | Requires credentials | Modifies DNS/network | Uploads artifacts |
| --- | --- | --- | --- | --- | --- |
| Verify AWS account, region, quotas, and caller identity | No | No | **Yes** | No | No |
| Initialize the approved remote state backend | **Yes** | Potentially | **Yes** | No | No |
| Run provider backed refresh and exact plan | No | No | **Yes** | No | No |
| Apply VPC, subnets, routes, endpoints, security groups, and flow logs | **Yes** | **Yes** | **Yes** | **Yes** | No |
| Apply RDS, secret metadata, identities, telemetry, backup storage, and ECR | **Yes** | **Yes** | **Yes** | No | No |
| Populate provider managed secret values | No new template resource | Potentially | **Yes** | No | No |
| Configure OIDC tenant and sanitized alert destination | Potentially | Potentially | **Yes** | Potentially | No |
| Build, scan, sign or attest, and push immutable images | No infrastructure | **Yes** | **Yes** | No | **Yes** |
| Create load balancer, certificate, WAF choice, and ECS services/tasks | **Yes** | **Yes** | **Yes** | **Yes** | No |
| Create or update staging DNS records | Potentially | Potentially | **Yes** | **Yes** | No |
| Upload approved synthetic datasets or deployment evidence | No infrastructure | Potentially | **Yes** | No | **Yes** |
| Run external health, recovery, and failure validation | Potentially | **Yes** | **Yes** | No | Potentially |

“Potentially” requires the same explicit approval as “Yes” because the exact
provider account configuration may create a resource, request, transfer, or
recurring charge.

## Gate 0: authorization record

- [ ] Name the staging owner, security reviewer, infrastructure operator,
  database operator, incident owner, and cost approver.
- [ ] Approve one dedicated non-production AWS account and one region.
- [ ] Approve the monthly budget, alert thresholds, and the `MEDIUM` baseline
  cost class using a current provider estimate.
- [ ] Approve the remote state backend, encryption, locking, access, retention,
  backup, and recovery policy.
- [ ] Record that broker, PAPER, LIVE, production, real-money, and order-routing
  authority all remain false.
- [ ] Record a rollback owner and a destroy/retention decision for every
  billable resource class.

**Stop gate:** any missing owner, budget, scope, account, region, state policy,
or retained false authority keeps the run at `HOLD`.

## Gate 1: credentials and native tool validation

- [ ] Obtain short-lived federated AWS credentials with MFA and the minimum
  role needed for read-only discovery and planning.
- [ ] Verify caller identity, account ID, region, service quotas, organization
  controls, and required tag policy against Gate 0.
- [ ] Install an approved pinned Terraform or OpenTofu version and verify its
  checksum.
- [ ] Run formatting and native validation against `infra/phase6/aws`.
- [ ] Initialize only the approved backend; do not silently use local state.
- [ ] Generate a saved provider backed plan with refresh enabled and no
  interactive or automatic apply.
- [ ] Scan the plan and state path for plaintext secrets, public database
  access, wildcard permissions, public task IPs, unbounded capacity, missing
  encryption, missing retention, and unexpected resources.

**External effect:** credentialed provider reads occur here. Backend
initialization may create or use paid external storage and locking resources.

**Stop gate:** account, region, identity, version, native validation, plan,
security scan, or inventory mismatch sets the status to `BLOCKED`.

## Gate 2: cost and change approval

- [ ] Export the exact plan inventory and map every resource to its owner,
  purpose, recurring cost driver, retention, and deletion policy.
- [ ] Produce a current regional provider estimate covering RDS availability
  mode, compute hours, load balancing, endpoints, logs, metrics, alarms,
  secrets, KMS requests, backups, ECR storage/scans, and transfer.
- [ ] Configure approved provider budget alarms before broad resource creation.
- [ ] Obtain written cost and change approval for the exact saved plan digest.
- [ ] Reject and regenerate the approval if the plan digest or any material
  variable changes.

**External effect:** budget configuration can create provider resources and
cost; the approved apply will create recurring cost.

**Stop gate:** missing estimate, budget, approver, inventory, or exact plan
digest keeps the status at `HOLD`.

## Gate 3: foundational provisioning

- [ ] Apply only the approved plan digest using a dedicated provisioning role.
- [ ] Create the VPC, subnets, routing, endpoints, security groups, flow logs,
  encryption keys, RDS PostgreSQL, secret metadata, workload identities,
  CloudWatch resources, encrypted backup bucket, and private ECR repository.
- [ ] Confirm ECS tasks have no public IP, RDS is private, ingress is limited to
  the approved load-balancer boundary, and egress matches the reviewed policy.
- [ ] Confirm every workload identity has only its exact artifact, telemetry,
  database, secret, backup, restore, or publishing permissions.
- [ ] Capture resource IDs, provider events, state backup, cost allocation tags,
  and the applied plan digest in the change record.

**External effect:** this gate creates external resources, changes networking,
uses credentials, and starts billable services.

**Stop gate:** partial apply, drift, public exposure, unexpected route,
permission expansion, missing encryption, failed logging, or unowned resource
requires containment and reconciliation before proceeding.

## Gate 4: secrets, identity, and notifications

- [ ] Generate database and OIDC material through approved secret procedures;
  never place values in Git, Terraform variables, plan files, logs, or tickets.
- [ ] Populate only the existing provider secret versions with the dedicated
  secret operator role.
- [ ] Configure the approved OIDC issuer, client, exact claims, redirect URIs,
  rotation, revocation, and audit retention.
- [ ] Add only the approved sanitized alert destination and test that alerts
  contain no credentials, tenant data, or trading payloads.
- [ ] Test revocation and denied access for every workload identity.

**External effect:** this gate requires credentials and mutates external secret,
identity, and notification systems; those services may incur cost.

**Stop gate:** exposed secret material, failed revocation, broad claims, shared
workload identity, or unsanitized alert content sets the status to `BLOCKED`.

## Gate 5: artifact build and upload

- [ ] Build the approved source commit reproducibly in an isolated build
  environment.
- [ ] Generate and retain the SBOM, vulnerability scan, source commit, build
  metadata, image digest, signature or attestation, and policy result.
- [ ] Fail the promotion if the scan or provenance policy is not green.
- [ ] Push the immutable digest to the private ECR repository using only the
  artifact publisher identity.
- [ ] Update deployment manifests to the reviewed digest and obtain deployment
  approval for that exact digest.

**External effect:** pushing images uploads artifacts, uses provider
credentials, stores billable data, and can incur scan and transfer costs.

**Stop gate:** mutable tag use, digest mismatch, missing provenance, failed
scan, or excessive publisher permission sets the status to `BLOCKED`.

## Gate 6: ingress, DNS, and workload deployment

- [ ] Provision the approved load balancer, TLS certificate, WAF decision, ECS
  cluster/services, task definitions, autoscaling bounds, and health checks.
- [ ] Validate the load balancer before creating or updating a staging DNS
  record; keep all internal services private.
- [ ] Apply the approved staging DNS change with a recorded prior value, TTL,
  rollback value, propagation check, and DNS owner.
- [ ] Deploy API, worker, and scheduler workloads by immutable image digest.
- [ ] Keep research desired count at zero until its own bounded synthetic job is
  approved. Use its separate identity and storage/schema boundaries.
- [ ] Do not add any broker endpoint, real market-data credential, PAPER/LIVE
  account, production secret, or order-routing permission.

**External effect:** this gate creates paid compute and ingress resources,
modifies network policy and DNS, and uses deployment credentials.

**Stop gate:** unhealthy service, unexpected egress, public task or database,
DNS mismatch, mutable image, cross-environment credential, or execution path
requires rollback and sets the status to `BLOCKED`.

## Gate 7: external staging validation

- [ ] Run read-only health checks and prove they create no trading side effect.
- [ ] Run migration only with the dedicated migration role, backup first, and
  verify forward recovery and audit evidence.
- [ ] Validate NQ and MNQ independently with approved synthetic datasets,
  including stale, gapped, illiquid, and malformed scenarios.
- [ ] Prove invalid, blocked, rejected, stale, incomplete, and unauthorized
  inputs cause zero broker, order, position, portfolio, account, journal,
  protection, OCO, PAPER, or LIVE effect.
- [ ] Exercise worker supervision, scheduler lease/fencing, alerting, artifact
  rollback, dependency outage, backup, PITR, and isolated restore validation.
- [ ] Restore only to a new isolated target and reconcile database, account,
  journal, risk, and portfolio state before reporting recovery success.
- [ ] Record measured capacity, recovery time, recovery point, failure evidence,
  residual risks, resource inventory, and actual cost against the approved
  estimate.

**External effect:** validation consumes billable compute, database, telemetry,
backup, registry, transfer, and storage services and may upload synthetic data
or evidence.

**Stop gate:** any execution side effect, ambiguous state, isolation breach,
failed restore, risk-control bypass, cost breach, or missing evidence sets the
status to `BLOCKED` and requires operator containment.

## Gate 8: closeout and ongoing control

- [ ] Choose and record one result: retain bounded staging, suspend compute
  while retaining approved data, or destroy resources under a separately
  reviewed retention plan.
- [ ] Revoke temporary operator credentials and artifact publisher access.
- [ ] Reconcile actual inventory and cost, confirm alarms and ownership, and
  record all retained resources and deletion dates.
- [ ] Review drift, secret rotation, restore evidence, access logs, dependency
  versions, artifact policy, and cost at the approved cadence.
- [ ] Require a new plan digest and approval for every material infrastructure,
  identity, network, DNS, artifact, or cost change.

Completion of external staging validation still does not authorize production
or trading. Production promotion, real market data, broker access, PAPER, LIVE,
or real-money execution requires a separate phase and independent safety
approval.

## Final authority state

`PROVISIONING_REQUIRES_SEPARATE_APPROVAL=TRUE`

`COST_APPROVAL_REQUIRED=TRUE`

`CREDENTIALS_REQUIRED=TRUE`

`DNS_NETWORK_APPROVAL_REQUIRED=TRUE`

`ARTIFACT_UPLOAD_APPROVAL_REQUIRED=TRUE`

`BROKER_AUTHORITY=FALSE`

`PAPER_AUTHORITY=FALSE`

`LIVE_AUTHORITY=FALSE`

`PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE`

`PUSH_PERFORMED=FALSE`

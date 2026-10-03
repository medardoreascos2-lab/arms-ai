# Phase 6 external staging architecture (R70C)

## Decision

### RECOMMENDED — AWS managed staging

Use a single AWS account dedicated to non-production staging, one approved
region, two availability zones, Terraform/OpenTofu-compatible configuration,
and these managed boundaries:

- one VPC with two public ingress subnets and two private workload/database
  subnets;
- an internet-facing Application Load Balancer that terminates TLS and is the
  only public application entry point;
- ECS Fargate services in private subnets for two API replicas, operational
  workers, one fenced scheduler candidate per replica, and separately bounded
  research workers;
- one-off ECS tasks with distinct identities for database migration, backup
  evidence, isolated restore validation, and deployment verification;
- private RDS for PostgreSQL, encrypted at rest, TLS-required, automated backup
  and PITR enabled, with Multi-AZ controlled by an explicit staging cost flag;
- Secrets Manager references for database and OIDC material; Terraform stores
  references and policies, never secret values;
- Amazon Cognito or an approved external OIDC issuer for human identity, with
  workload identity supplied by distinct IAM task roles;
- CloudWatch logs, metrics, dashboards and alarms, with an approved sanitized
  SNS operator destination added only during authorized provisioning;
- private ECR repositories with digest-pinned runtime images; and
- encrypted, versioned S3 buckets for backup evidence, research provenance,
  deployment manifests and audit exports, with public access blocked.

The application remains provider neutral at its PostgreSQL, OIDC, secret,
metric, artifact and object interfaces. AWS-specific identifiers are confined
to IaC, deployment rendering and provider adapters.

## Logical topology

```text
Approved test client
        |
   TLS 443 only
        v
Public ALB + WAF-ready boundary
        |
        v
Private ECS API replicas ----> CloudWatch logs/metrics
        |       |                       |
        |       +----> private RDS      +----> sanitized SNS route
        |                  ^
        v                  |
Private worker tasks ------+
Private scheduler tasks ---+  (durable lease/fencing in PostgreSQL)

Isolated research tasks --> separate CPU/memory limits + research prefix/schema

ECS identities --> Secrets Manager references / ECR pull / scoped S3 objects
Operator roles --> deploy, migrate, backup, restore, observe (separate grants)
```

No path, security group, task role, secret, environment variable or DNS record
may name or authorize a broker endpoint. The environment has no PAPER, LIVE,
production, portfolio or financial-execution authority.

## Network and trust boundaries

1. The ALB accepts HTTPS only. HTTP may exist solely as a redirect during an
   approved deployment; health checks use a read-only endpoint.
2. ECS tasks receive no public IP. Only the ALB security group can reach the API
   target port. Internal services are not externally addressable.
3. RDS is not publicly accessible. Its security group accepts PostgreSQL only
   from the exact application and migration groups.
4. Runtime egress is deny-by-default in the intended policy. Required AWS API
   paths use reviewed VPC endpoints where practical; any remaining NAT route is
   explicit, logged, costed and destination constrained before provisioning.
5. Each task family has its own IAM role. The ECS execution role can pull its
   image and emit logs, but has no application data authority.
6. Human operator access uses MFA and federated roles. There are separate
   read-only observer, deployer, migration, backup and restore roles.
7. Backup and restore permissions are separated. Restore always targets a new,
   isolated database and cannot overwrite staging in place.

## Workload placement

| Workload | Replicas / mode | Identity | Data authority | External authority |
| --- | --- | --- | --- | --- |
| API | Two service tasks across zones | `arms-staging-api` | Tenant-scoped read/write through application DB role | HTTPS responses only; no trade execution |
| Operational worker | At least two supervised service tasks | `arms-staging-worker` | Durable outbox/lease operations only | Sanitized approved alert adapter only |
| Scheduler | Two candidates, one lease owner | `arms-staging-scheduler` | Scheduler lease and job records | None |
| Research worker | Desired count zero by default; explicit jobs | `arms-staging-research` | Research schema/prefix only | None |
| Migration | One-off task | `arms-staging-migration` | Forward-only schema changes | None |
| Backup | Scheduled or operator-run one-off task | `arms-staging-backup` | Database read plus write-only backup prefix | None |
| Restore validator | Operator-run isolated task | `arms-staging-restore` | Read backup prefix and create isolated validation target | None |

NQ and MNQ remain distinct canonical instruments through API, worker, database,
research and telemetry paths. Any cross-instrument report must label its scope;
risk sizing always uses the selected instrument's exact point value.

## Availability and recovery profile

- API tasks span two zones and the load balancer removes unhealthy targets.
- Worker and scheduler duplicates use the durable lease/fencing behavior already
  validated in Phase 4 and Phase 5.
- RDS starts with the operator-selected `single_az` or `multi_az` staging mode.
  `single_az` is cost-optimized but keeps the provisioning gate at `HOLD` until
  its recovery objective is accepted. It never silently claims HA.
- Automated database backup/PITR and encrypted S3 evidence archives are both
  required. A successful backup does not imply a successful restore.
- Rollback uses immutable prior image digests. Schema-incompatible rollback
  escalates to the verified isolated-restore procedure.

## Cost and scale controls

The baseline is `MEDIUM` monthly cost. Multi-AZ RDS, NAT gateways in both zones,
large telemetry retention, WAF, private endpoints and continuously running
research raise the design toward `HIGH`. IaC must expose these decisions as
reviewable variables, tag every resource, set bounded log retention, keep
research desired capacity at zero, and produce a plan before any cost approval.

## Alternatives

### ALTERNATIVE — Azure managed staging

Azure Container Apps, PostgreSQL Flexible Server, Key Vault, Entra ID, Azure
Monitor, Blob Storage and ACR can implement the same boundaries. Select this
when an existing Azure tenant, Entra operations, approved region and cost model
materially reduce operational risk. Preserve separate managed identities and
do not map all jobs to one identity.

### ALTERNATIVE — Google Cloud managed staging

Cloud Run services/jobs/worker pools, Cloud SQL, Secret Manager, Identity
Platform or external OIDC, Cloud Monitoring, Cloud Storage and Artifact
Registry can implement the same boundaries. Select this when measured workload
behavior confirms that request-driven scaling and worker semantics meet the
durability and latency requirements.

## Deferred

- Self-managed VPS/container hosts are deferred for durable staging because
  host, database, secret, identity, observability and recovery duties create an
  unacceptable combined failure domain.
- Kubernetes/EKS is deferred until workload scale or policy needs justify its
  control-plane cost and operational surface.
- Cross-region active/active, production DNS, broker connectivity, PAPER/LIVE
  execution, real market data and production deployment are outside Phase 6.

## Operator approval boundaries

An operator must later approve provider account, region, budget, credentials,
Terraform state backend, DNS zone, certificate name, OIDC issuer, alert
destination, artifact upload and the exact `plan`. No `apply`, resource create,
artifact push or external mutation is authorized by this document.

`ARCHITECTURE_SELECTION=RECOMMENDED_AWS_MANAGED_STAGING`

`ALTERNATIVES=AZURE_MANAGED,GCP_MANAGED`

`DEFERRED=SELF_MANAGED_VPS,EKS,CROSS_REGION,PRODUCTION,LIVE`

`EXTERNAL_RESOURCES_CREATED=FALSE`

`COST_INCURRED=FALSE`

`BROKER_AUTHORITY=FALSE`

`PAPER_AUTHORITY=FALSE`

`LIVE_AUTHORITY=FALSE`

`PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE`

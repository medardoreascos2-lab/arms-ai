# Phase 6 external staging provider matrix (R70B)

## Decision scope

This comparison was reviewed on 2026-10-03 against the R70A requirements. It
compares feasible staging paths without creating resources, opening accounts,
using credentials, changing DNS, publishing artifacts, or granting execution
authority. Cost is categorical because region, retention, traffic, discounts,
taxes, and high-availability choices remain operator inputs.

## Candidate matrix

| Criterion | AWS managed stack | Azure managed stack | Google Cloud managed stack | Self-managed VPS/container host |
| --- | --- | --- | --- | --- |
| Representative runtime | ECS on Fargate with separate services/tasks | Container Apps services and jobs | Cloud Run services, jobs, and worker pools | Rootless containers under systemd or a small orchestrator |
| Monthly cost category | `MEDIUM`; `HIGH` with NAT gateways, Multi-AZ database, private endpoints, and long telemetry retention | `MEDIUM`; `HIGH` with zone-redundant database and larger Log Analytics retention | `LOW` to `MEDIUM` for low request volume; `MEDIUM` with continuously allocated workers and Cloud SQL HA | `LOW` for one host; `MEDIUM` or `HIGH` when credible HA, backups, monitoring, patching, and operator time are included |
| Security features | Mature IAM roles, task/execution role separation, VPC controls, KMS, CloudTrail, WAF options | Managed identities, RBAC, VNet integration, Key Vault, Activity Logs, Defender options | Service identities, IAM, VPC controls, Cloud KMS, Audit Logs, VPC Service Controls options | Full control, but the operator owns hardening, patching, audit, key custody, firewall correctness, intrusion response, and isolation |
| Managed PostgreSQL | RDS for PostgreSQL; private VPC placement, automated backup/PITR, optional Multi-AZ | PostgreSQL Flexible Server; private VNet access, PITR, optional zonal or zone-redundant HA | Cloud SQL for PostgreSQL; private networking, automated backups/PITR, optional regional HA | Provider-managed PostgreSQL where available is preferred; self-hosted PostgreSQL materially increases recovery and patch risk |
| Secret management | Secrets Manager with versioning, IAM and KMS | Key Vault with managed identity and RBAC | Secret Manager with service identity and version grants | Requires a separate Vault-compatible service or tightly controlled host files; bootstrap and rotation burden is highest |
| Human identity | Cognito or an external standards-based OIDC issuer | Microsoft Entra ID / External ID | Identity Platform or external OIDC | External OIDC required; operating an issuer on the same host is rejected as a staging trust boundary |
| Workload identity | Per-task IAM roles | Per-app or user-assigned managed identities | Per-service user-managed service accounts | Host or orchestrator identity plumbing is operator-built and commonly becomes shared credentials |
| Monitoring and alerts | CloudWatch Logs, metrics, alarms, dashboards and SNS routing | Azure Monitor, Log Analytics, alerts and Action Groups | Cloud Logging, Monitoring, alerts and notification channels | Prometheus/OpenTelemetry/log stack must be operated, retained, backed up and secured separately |
| Artifact registry | Private ECR with digest references and scanning options | Azure Container Registry with managed-identity pull | Artifact Registry with service-account pull | External OCI registry or self-hosted registry; availability, signing policy and retention are operator-owned |
| Object storage | S3 with versioning, encryption, lifecycle and access policy | Blob Storage with versioning, encryption, lifecycle and RBAC | Cloud Storage with versioning, encryption, lifecycle and IAM | Provider object storage is preferred; local disks do not meet off-host backup requirements |
| Networking | VPC, public ALB boundary, private workload/database subnets, security groups, VPC endpoints | VNet-integrated environment, external/internal ingress, private database networking and private endpoints | Cloud Run ingress controls, VPC connector/direct egress, private services access | Simple firewalling, but safe private east-west paths, egress control and multi-host routing require more design and testing |
| Backup | RDS automated backups/PITR plus encrypted S3 evidence archives and optional AWS Backup | Flexible Server automatic backup/PITR plus Blob archives and optional Azure Backup | Cloud SQL backup/PITR plus Cloud Storage archives | Database dumps, WAL/PITR, immutable off-host copies, schedules and restores are entirely operator-owned |
| Regional availability | Broad; exact ECS/Fargate, RDS class, Cognito and zone combination must be checked for selected region | Broad; Container Apps and zone-redundant PostgreSQL availability varies by region/SKU | Broad; Cloud Run, Cloud SQL HA and Identity Platform availability must be checked together | Host-specific; single-region and single-host concentration is common |
| Vendor lock-in | `MEDIUM`; OCI, PostgreSQL and OpenTelemetry remain portable, while IAM, networking and service definitions are AWS-specific | `MEDIUM`; OCI/PostgreSQL portable, managed identity, VNet and monitor definitions are Azure-specific | `MEDIUM`; OCI/PostgreSQL portable, service account, Cloud Run and network definitions are GCP-specific | `LOW` at the application layer; `HIGH` operational dependence on bespoke scripts and operator knowledge |
| Operational complexity | `MEDIUM-HIGH`; broad capability with many explicit network/IAM resources | `MEDIUM`; Container Apps reduces runtime operations, while RBAC/networking still need care | `LOW-MEDIUM`; managed runtime is concise, but long-running worker behavior and network egress need validation | `HIGH`; patching, HA, secret/bootstrap, monitoring, backups, restore and capacity all become project duties |
| Fit for ARMS staging | Strongest fit for persistent API/worker/scheduler separation and explicit IAM boundaries | Strong alternative, especially where Entra and Azure operations already exist | Strong alternative for request-driven workloads and small idle footprint | Acceptable only for a temporary local-equivalent rehearsal; weak fit for the required durable trust and recovery boundaries |

## Evidence reviewed

- AWS documents distinct ECS task and task-execution roles, including narrow
  access for ECR, CloudWatch Logs and secret references:
  <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security-iam-roles.html>.
- AWS documents automated RDS backups and point-in-time restore behavior:
  <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html>.
- Azure documents Container Apps managed identities, RBAC and identity-based
  private registry access:
  <https://learn.microsoft.com/en-us/azure/container-apps/managed-identity>.
- Azure documents private PostgreSQL VNet integration and its required service
  paths:
  <https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-networking-private>.
- Azure documents Flexible Server automatic backups, retention and PITR:
  <https://learn.microsoft.com/en-us/azure/postgresql/backup-restore/concepts-backup-restore>.
- Google documents Cloud Run service identity and recommends a user-managed
  service account with minimal permissions:
  <https://docs.cloud.google.com/run/docs/securing/service-identity>.
- Google documents the integrated Cloud Run, Cloud SQL, Secret Manager,
  Artifact Registry, Identity Platform and least-privilege path:
  <https://docs.cloud.google.com/run/docs/tutorials/identity-platform>.
- DigitalOcean documentation illustrates the operational boundary for a
  smaller-host option: private App Platform VPC connectivity, TLS-protected
  managed PostgreSQL and trusted-source restrictions:
  <https://docs.digitalocean.com/products/app-platform/how-to/enable-vpc/> and
  <https://docs.digitalocean.com/products/databases/postgresql/how-to/secure/>.

## Comparative findings

All three hyperscaler candidates can meet the R70A minimums. AWS has the most
direct mapping to ARMS's continuously running API, workers and single-owner
scheduler, with explicit task identities and mature managed durability. Azure
offers a comparable design with fewer runtime primitives and is particularly
attractive when Entra operations already exist. Google Cloud can minimize idle
runtime cost, but the exact behavior and cost floor for persistent worker pools
must be validated before selection.

The self-managed candidate has an attractive initial invoice but does not have
an attractive total control burden. A single host cannot satisfy the target HA
and recovery posture. Adding multiple hosts, an independent identity boundary,
off-host secrets, managed PostgreSQL, object storage and monitoring removes
most of the apparent simplicity.

## R70B outcome

The candidates advance to R70C with these dispositions:

- AWS: preferred candidate for topology selection.
- Azure: qualified alternative.
- Google Cloud: qualified alternative where scale-to-zero is more important
  than continuously running worker simplicity.
- Self-managed host: deferred for durable external staging; retain only as a
  disposable rehearsal option.

This is a comparative result, not provisioning authorization.

`PROVIDER_COMPARISON_COMPLETE=TRUE`

`EXTERNAL_RESOURCES_CREATED=FALSE`

`COST_INCURRED=FALSE`

`CREDENTIALS_USED=FALSE`

`BROKER_AUTHORITY=FALSE`

`PAPER_AUTHORITY=FALSE`

`LIVE_AUTHORITY=FALSE`

`PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE`

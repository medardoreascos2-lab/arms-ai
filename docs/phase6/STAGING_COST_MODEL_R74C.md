# Phase 6 external staging cost model (R74C)

## Contract

This document classifies expected AWS staging cost by architecture shape. It is
not a quote, budget approval, purchase order, or authorization to provision.
No exact prices are stated because no approved region, account discounts,
provider price export, usage measurements, tax treatment, or reviewed plan is
available. The operator must generate a provider estimate from the exact plan
before any external action.

`BASELINE_COST_CLASS=MEDIUM`

`EXACT_PRICE_ESTIMATE=UNAVAILABLE`

`COST_APPROVAL_REQUIRED=TRUE`

`PURCHASE_PERFORMED=FALSE`

`EXTERNAL_RESOURCES_CREATED=FALSE`

## Cost-driving resources

| Area | Template evidence | Primary cost drivers | Control in the current design |
| --- | --- | --- | --- |
| Compute | API, operational worker, scheduler, research workload manifests | Task count, vCPU, memory, task hours, autoscaling, job runtime | Bounded replica maxima; research desired count is zero |
| PostgreSQL | RDS database module | Instance class, Single-AZ or Multi-AZ, storage, storage growth, backup retention, performance telemetry | Small reviewed default class, bounded storage and connection settings, explicit Multi-AZ choice |
| Network | VPC, subnets, private endpoints, public ingress boundary | Interface endpoint hours/data, load balancer capacity, processed bytes, public egress, optional NAT | No NAT gateway is declared; workloads use private endpoints and have constrained egress |
| Logs and metrics | CloudWatch log groups, filters, alarms and dashboard | Ingest volume, stored bytes, retention, metric cardinality, queries, alarms | Bounded retention and fixed safety metric dimensions |
| Secrets and keys | Secrets Manager references and KMS keys | Secret count, retrieval calls, rotation calls, key count and cryptographic requests | Fixed reviewed secret inventory; rotation hook remains optional |
| Backups | RDS retention and encrypted versioned S3 bucket | Snapshot/object bytes, versions, retention, requests, retrieval and data transfer | Bounded retention and lifecycle expiration; restore is operator initiated |
| Artifact registry | Private ECR repository | Stored image layers, scan activity, retention count, transfer | Immutable tags and bounded retained image count |
| Identity and alerts | IAM roles/policies and SNS topic | Usually request/message driven; external identity licensing is provider/operator dependent | Dedicated roles and no alert subscription until approved |

The templates do not yet provision ECS services, a load balancer, DNS records,
certificates, an external identity tenant, alert subscriptions, or artifacts.
Their expected cost still belongs in the operator estimate because the reviewed
deployment topology requires some of them during a later authorized step.

## LOW

A LOW profile is a short-lived validation window with the smallest reviewed
Single-AZ database choice, bounded API/worker/scheduler task hours, research at
zero except for brief synthetic jobs, minimal approved log retention, low
artifact and backup volume, and no NAT, WAF, cross-region copy, or continuous
load generation.

This profile trades availability and retention depth for lower spend. It must
remain `HOLD` if the selected recovery objective requires Multi-AZ or longer
retention. Stopping compute does not remove storage, secret, endpoint, key,
backup, or registry charges.

## MEDIUM

MEDIUM is the baseline class for a durable multi-host staging environment. It
includes two API replicas, supervised operational workers, two scheduler
candidates, the reviewed PostgreSQL instance and backup settings, private AWS
service endpoints, encrypted retained logs, alarms, an artifact registry, and
periodic synthetic research or recovery exercises.

Single-AZ versus Multi-AZ PostgreSQL can move this profile materially within or
beyond MEDIUM. The exact classification requires a plan and regional estimate.

## HIGH

A HIGH profile includes one or more of these explicit decisions:

- Multi-AZ database capacity with a larger instance or rapid storage growth;
- continuously running or scaled research workers;
- sustained API/worker load and high task replica counts;
- long log, artifact, snapshot, object-version, or backup retention;
- high metric cardinality, query volume, or data transfer;
- NAT gateways, WAF, extensive interface endpoints, or high load balancer use;
- cross-region replication or disaster-recovery infrastructure; or
- frequent artifact scanning, backup/restore drills, or large dataset movement.

Cross-region and production capabilities remain deferred and unauthorized even
when they are listed as possible HIGH cost drivers.

## Required operator estimate inputs

Before provisioning, record the approved account and region, exact Terraform
plan, task sizes and hours, autoscaling assumptions, database class and
availability mode, storage and monthly growth, backup/log/artifact retention,
endpoint count, expected ingress/egress, load balancer capacity assumptions,
research duty cycle, alert/identity service choices, taxes, discounts, budget
threshold, and named approver. Re-estimate after every material plan change.

`BROKER_AUTHORITY=FALSE`

`PAPER_AUTHORITY=FALSE`

`LIVE_AUTHORITY=FALSE`

`PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE`

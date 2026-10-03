# Phase 5 synthetic staging load profiles (R59A)

## Scope and evidence boundary

These profiles define bounded, repeatable workloads for the isolated local
Phase 5 topology. They are synthetic test inputs. They do not represent measured
customer demand, production capacity, a service-level objective, or cloud
equivalence. Results may be compared only when the source revision, host,
database mode, profile, workload window, worker count, and in-flight limit are
identical.

Every run uses local generated records and in-process clients. External traffic,
provider credentials, broker connections, LIVE authority, and financial account
mutation remain disabled.

## Common workload model

- **Measurement window:** 10 seconds of modeled demand after setup. A harness
  may execute the resulting fixed operation set faster or slower than wall clock,
  but it must report actual elapsed time and actual throughput.
- **Rates:** Snapshot, evaluation, API read, notification, and outbox values are
  aggregate operations per modeled second across all tenants. Research values
  are aggregate jobs per modeled minute. The fixed 10-second research count is
  `max(1, ceiling(jobs_per_minute * 10 / 60))` so every profile exercises that
  workload class.
- **Accounts:** `tenant count * accounts per tenant` is the exact account set.
  Operations distribute deterministically across that set.
- **Outbox volume:** The stated rate is total outbox ingress. Notification events
  are included in that total; remaining outbox items are synthetic operational
  events. No event is externally delivered.
- **Isolation:** Every operation carries an explicit tenant and, where required,
  account. Cross-tenant reads or writes are failures even if aggregate metrics
  otherwise pass.
- **Reproducibility:** Operation IDs, tenant/account selection, payloads, and
  failure injection use a recorded deterministic seed. No live market or account
  data may be substituted.

## Profiles

| Field | SMALL | MEDIUM | STRESS |
|---|---:|---:|---:|
| Tenant count | 2 | 10 | 25 |
| Accounts per tenant | 4 | 20 | 40 |
| Total accounts | 8 | 200 | 1,000 |
| Snapshot rate / second | 2 | 20 | 100 |
| Evaluation rate / second | 2 | 15 | 80 |
| API read rate / second | 20 | 100 | 500 |
| Research jobs / minute | 1 | 10 | 60 |
| Notification events / second | 1 | 10 | 50 |
| Total outbox volume / second | 2 | 20 | 100 |
| Harness workers | 4 | 8 | 16 |
| Maximum in flight | 16 | 64 | 256 |

The 10-second modeled operation counts are therefore:

| Operation class | SMALL | MEDIUM | STRESS |
|---|---:|---:|---:|
| Snapshot ingestion | 20 | 200 | 1,000 |
| Evaluation | 20 | 150 | 800 |
| API reads | 200 | 1,000 | 5,000 |
| Research jobs | 1 | 2 | 10 |
| Notification events | 10 | 100 | 500 |
| Total outbox ingress | 20 | 200 | 1,000 |
| Total scheduled operations | 261 | 1,552 | 7,810 |

`Total scheduled operations` counts outbox ingress once. Notification events are
a labeled subset of outbox ingress and are not added a second time.

## Required measurements

Each R59B run records the following for the complete run and, where applicable,
per operation class:

1. attempted, succeeded, and failed operation counts;
2. actual elapsed time and successful throughput per second;
3. P50, P95, and P99 service latency using nearest-rank percentiles;
4. error rate with stable error codes and no secret-bearing messages;
5. maximum harness queue depth and maximum queue wait;
6. final durable outbox depth, maximum observed outbox depth, and terminal state
   counts;
7. a database saturation indication based on observed busy/locked failures and
   peak configured connection or worker occupancy;
8. maximum worker lag from an event's availability time to its claim time;
9. maximum scheduler lag from a job's due time to lease acquisition; and
10. tenant/account isolation checks and the count of duplicate durable writes.

P50, P95, and P99 are calculated from successful and failed operation service
times together so failures cannot disappear from latency evidence. An empty
operation class reports no percentile instead of inventing zero latency.

## Profile gates

| Gate | SMALL | MEDIUM | STRESS |
|---|---:|---:|---:|
| Required completed operation ratio | 100% | 100% | 99% or higher |
| Maximum error rate | 0% | 0% | 1% |
| Tenant or account isolation violations | 0 | 0 | 0 |
| Duplicate durable writes | 0 | 0 | 0 |
| Unauthorized external effects | 0 | 0 | 0 |
| Unbounded queue growth | prohibited | prohibited | prohibited |

The latency and throughput values are measurements, not pass thresholds in R59A.
This prevents the first local run from turning an unmeasured host characteristic
into a production claim. R59B must preserve the raw sample counts and report any
resource or environmental limitation that prevents a profile from completing.

## Fail-closed rules

1. A missing tenant/account identity, stale or invalid authorization context,
   replay rejection, database integrity error, or unknown workload field fails
   that operation before its durable or outbox side effect.
2. A rejected operation must leave state, outbox, audit, portfolio, account, and
   execution records unchanged.
3. Research work may be throttled or rejected under pressure. Operational
   snapshot, evaluation, read, audit, and outbox capacity remains reserved.
4. Hitting a configured hard queue, worker, memory, or disk limit stops new
   admission and records a bounded local failure; it does not grow the workload
   without limit.
5. No profile enables broker, order, PAPER position, LIVE, deployment, cloud
   provisioning, or external notification authority.

## R59B selection

R59B starts with SMALL, then MEDIUM, and attempts STRESS only after the preceding
profile preserves all safety gates. A host limit may classify STRESS as
`BLOCKED_LOCAL_CAPACITY`; it must not be relabeled as a pass and must not trigger
external provisioning. The exact profile, source commit, Python version, OS,
database backend, seed, configured concurrency, and actual metrics belong in the
result record.

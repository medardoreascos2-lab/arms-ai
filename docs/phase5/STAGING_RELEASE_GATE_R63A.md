# Phase 5 staging release gate (R63A)

## Purpose

The deterministic gate decides whether the completed local evidence is ready
for a later request to provision external staging. It does not provision,
deploy, contact a provider, grant production authority, or grant broker, PAPER,
LIVE, order, or execution authority.

## Allowed states

| State | Meaning |
| --- | --- |
| `READY_FOR_EXTERNAL_STAGING_PROVISIONING` | Every required local gate passed and every known external blocker remains disclosed. This permits planning and an explicit approval request only. |
| `HOLD` | One or more required local evidence gates are incomplete. |
| `BLOCKED` | A frozen baseline changed or prohibited execution, broker, PAPER, LIVE, production, or deployment authority is present. |

No state represents production readiness.

## Required local evidence

The ready state requires green local staging tests, completed security review,
verified backup/restore, verified API/worker/scheduler replicas, verified
load/failover, verified artifact integrity, the unchanged V8 frozen baseline,
and unchanged published Phase 2-4 baselines.

Incomplete local evidence returns `HOLD`. A baseline or authority violation has
precedence and returns `BLOCKED`, while retaining all deterministic reasons.

## External blockers retained

The gate requires the exact current blocker inventory:

1. PostgreSQL runtime;
2. managed secret provider;
3. external identity provider;
4. external telemetry and alerting;
5. off-host backup and managed keys;
6. artifact registry and signing;
7. DNS, TLS, private networking, and orchestration.

Omitting a blocker makes the evidence invalid. A ready result therefore cannot
be interpreted as cloud equivalence or as authorization to provision anything.

## Authority boundary

The gate and every result permanently expose false provisioning, production,
deployment, execution, broker, PAPER, and LIVE authority fields. Evaluation is
pure and has no database, portfolio, account, journal, outbox, network, order,
position, protection, OCO, or external-delivery side effect.

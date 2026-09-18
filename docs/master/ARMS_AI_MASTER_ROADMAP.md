# ARMS AI — MASTER ROADMAP

## Current Phase 1 acceptance — V8.1

[Runtime admission certification](../architecture/phase1_runtime_market_risk_admission_v81.md)
and the requirements matrix record **PHASE1_STATUS=CLOSED** for the defined PAPER
scope: all 12 requirements CLOSED_CERTIFIED; zero partial, blocked, documentation-only
or unclassified gaps. Baseline: `d40745fa0bc1a481ef2d171753e392890b9109e0`.

One canonical lifecycle admission boundary now enforces account/runtime validity,
current certified market evidence, existing risk limits and order guards for HTTP
and direct submissions. The original two V8 RED tests pass unchanged. Direct tests:
187 passed; consolidated: 3,803 passed / 0 failed / 1 unchanged skip across 432
modules; full backend: 5,508 passed / 0 failed / 1 unchanged skip.

Next planned action: **PHASE2 — Data and Market Intelligence**. This closure does
not approve a product release or LIVE execution. Older status/count statements
below describe historical closure-wave and V8 evidence and do not override this
current certificate.

## Historical Phase 1 acceptance — V8

[Consolidated acceptance certificate](../architecture/phase1_consolidated_acceptance_v8.md)
and the requirements matrix recorded the V8 Phase 1 status at synchronized
baseline `d40745fa0bc1a481ef2d171753e392890b9109e0`.
**PHASE1_STATUS=OPEN**: 12 requirements; 8 scoped CLOSED_CERTIFIED,
3 PARTIAL_REAL_GAP, 1 BLOCKED, 0 unclassified. Earlier closure-wave statuses and
test counts below remain historical evidence.

New HTTP/direct PAPER characterization demonstrates execution without mandatory
quote/calendar/news authorization; optional lifecycle guard wiring also differs
by construction path. The V8 large-integration scope stop applies. Next package:
`PHASE1_RUNTIME_MARKET_RISK_ADMISSION_INTEGRATION`. No production implementation,
commit/push, Phase 2 readiness or LIVE approval is claimed by this audit. The
linked certificate contains exact tests, failure attribution and account-isolation
proof across all 101 direct application bindings and 21 owner domains.

---

> Evidence-based roadmap for ARMS AI.
> Current repository code, current tests, runtime characterization, closure-wave
> evidence, and operational evidence are authoritative for implementation status.
> Historical evidence preserves intent and prior demonstrations but does not
> prove current implementation.

---

## 1. ROADMAP STATUS

Current status:

`PHASE 1 CLOSED — V8.1 PAPER SCOPE CERTIFIED`

Historical consolidation status:

`COMPLETE — GREEN AUDIT CHAIN 210-290 RECONCILED`

Phase 0 status:

`CLOSED — FORMALLY CERTIFIED`

Phase 1 status:

`CORE RELIABILITY — ALL 12 REQUIREMENTS CLOSED_CERTIFIED; NEXT PHASE 2`

The roadmap is reconciled against:

- `AGENTS.md`;
- `HISTORICAL_EVIDENCE_2026.md`;
- `CONSOLIDATED_AUDIT_CONTEXT.md`;
- current repository implementation and tests;
- Phase 0 certification;
- GREEN audits 210 through 290;
- Phase 1 runtime, risk, recovery, account-isolation, API/dashboard, financial-
  synchronization, compatibility, and closure-wave evidence.

The closure wave reviewed supplied evidence showing:

```text
PHASE1_VERIFIED_COUNT=2
PHASE1_PARTIAL_COUNT=10
PHASE1_OPEN_COUNT=0
PHASE1_NEEDS_VERIFICATION_COUNT=0
BACKEND_TEST_COUNT=630
BACKEND_TESTS_PASSED=5041
BACKEND_TEST_EXIT=0
```

The full regression is green based on supplied repository evidence. It was not
executed by this documentation update.

Historically, that closure wave did not satisfy every Phase 1 exit gate.
The V8.1 certificate above supersedes that disposition for the defined PAPER scope.

Autonomous LIVE trading remains blocked.

---

## 2. EVIDENCE AND STATUS POLICY

Evidence is interpreted in this order:

1. Current repository implementation and current tests.
2. Current runtime composition and operational evidence.
3. Current characterization and integration evidence.
4. Phase 1 closure-wave evidence.
5. Formal Phase 0 certification.
6. Completed GREEN audit evidence.
7. Historical documentation and historical demonstrations.

A component filename, class name, roadmap statement, historical API response,
or prior test report does not prove current implementation by itself.

Capabilities use these statuses:

- `VERIFIED_IMPLEMENTED`
- `VERIFIED_CLOSED`
- `PARTIALLY_IMPLEMENTED`
- `PLANNED_NOT_IMPLEMENTED`
- `HISTORICAL_IDEA`
- `NEEDS_VERIFICATION`
- `SUPERSEDED`
- `DUPLICATE`
- `CONFLICT`
- `BLOCKED`
- `DEFERRED`

`VERIFIED_CLOSED` is reserved for formally certified closure. Phase 0 is the
currently certified closed scope.

A characterization or closure-wave result may be stronger than an unverified
component classification without constituting approval or closure. Partial
evidence must remain partial where application-wide behavior is not proven.

---

## 3. GOVERNING PRIORITIES

Priority order:

1. Critical safety defects
2. Trading execution integrity
3. Risk integrity
4. Account state integrity
5. Recovery and persistence
6. Strategy validation integrity
7. API and runtime consolidation
8. Automated testing
9. Data integrations
10. Intelligence improvements
11. Product features
12. Commercialization
13. Advanced autonomy

No feature expansion may weaken:

- risk controls;
- account isolation;
- state integrity;
- recovery behavior;
- authorization;
- market-data freshness;
- the rejected-signal zero-side-effect invariant.

---

## 4. PHASE 0 — CRITICAL STABILIZATION

Status:

`VERIFIED_CLOSED — FORMALLY CERTIFIED`

Phase 0 contained eight critical stabilization requirements:

1. Prevent blocked signals from executing.
2. Remove execution side effects from dashboard read operations.
3. Correct daily PnL synchronization.
4. Correct daily loss and trading-block synchronization.
5. Correct account-switching consistency.
6. Complete execution-state recovery within the certified scope.
7. Resolve startup/runtime path inconsistencies within the certified scope.
8. Review and enforce API security boundaries within the certified scope.

Certification evidence:

- `PHASE0_REQUIREMENTS=8`
- `PHASE0_VERIFIED_CLOSED=8`
- `PHASE0_PARTIAL_COUNT=0`
- `PHASE0_OPEN_COUNT=0`
- `PHASE0_NEEDS_VERIFICATION_COUNT=0`
- `PHASE0_AUDIT_COMPLETE=YES`
- `PHASE0_CLOSE_RECOMMENDATION=CLOSE`
- documented backend regression: `5082 tests passed`
- closure commit:
  `c13cd54d7ec0453c86e934ce117ce11764de5a4e`
- closure message:
  `test: close Phase 0 critical stabilization gaps`

Phase 0 closure is limited to its certified scope. It does not certify:

- the complete historical product vision;
- the controlled PAPER MVP;
- Phase 1 implementation;
- production readiness;
- autonomous LIVE trading;
- physical broker execution;
- complete cross-subsystem synchronization;
- complete route or authorization coverage beyond the certified scope.

---

## 5. HISTORICAL CONSOLIDATION AND GREEN AUDIT CHAIN

Status:

`COMPLETE`

GREEN audits 210 through 290 established that:

- historical requirements must be separated from current implementation;
- current repository code and tests are authoritative;
- architecture duplication and supersession risks must be documented;
- MVP gaps must remain explicit;
- the Requirements Matrix, Master Memory, Decision Log, and roadmap must
  preserve evidence boundaries;
- Phase 1 must be characterized before implementation expansion or
  consolidation;
- no production code or tests were modified by the audit chain;
- autonomous LIVE trading remained disabled;
- destructive consolidation was not authorized.

The audit chain does not mark unresolved capabilities as implemented.

---

## 6. PHASE 1 — CORE RELIABILITY

Current status:

`CHARACTERIZED — CLOSURE WAVE REVIEWED — NOT CERTIFIED COMPLETE`

Phase 1 objective:

> Establish a repository-derived authoritative runtime architecture for the
> controlled PAPER trading system.

Phase 1 is an architecture, ownership, characterization, and reliability
phase. It does not expand product scope and does not enable LIVE execution.

### 6.1 Closure-wave evidence result

The closure wave reviewed evidence for:

- ASGI and direct FastAPI application paths;
- the separate CLI/process path;
- runtime context construction;
- startup, shutdown, recovery, and durability layers;
- the strongest observed PAPER lifecycle;
- risk-authority ownership and unresolved overlaps;
- financial-state and fill-synchronization behavior;
- coordinated account-switch containment;
- API/dashboard route ownership and authorization attachment;
- compatibility and supersession classifications;
- current focused tests;
- supplied current full backend regression evidence.

The recorded totals are:

```text
PHASE1_VERIFIED_COUNT=2
PHASE1_PARTIAL_COUNT=10
PHASE1_OPEN_COUNT=0
PHASE1_NEEDS_VERIFICATION_COUNT=0
BACKEND_TEST_COUNT=630
BACKEND_TESTS_PASSED=5041
BACKEND_TEST_EXIT=0
```

The full regression is green based on supplied repository evidence. It was not
executed by this documentation update.

The two verified Phase 1 requirements are:

- `PH1-REQ-010` — compatibility and supersession register;
- `PH1-REQ-012` — canonical documentation baseline.

The remaining ten requirements are partially verified because the evidence
characterizes substantial behavior but does not prove complete application-wide
composition, ownership, synchronization, authorization, isolation, or
equivalence across every path.

### 6.2 Characterized canonical PAPER candidate

The strongest observed controlled PAPER path is:

```text
validated supplied market data
→ market context and intelligence
→ signal or decision
→ lifecycle admission
→ account and risk checks
→ trade-plan and order validation
→ execution risk gate
→ PAPER connector and simulated fill
→ position and logical protection state
→ portfolio and account synchronization
→ journal and trade history
→ dashboard events
→ durable persistence
→ recovery and semantic validation
```

The strongest observed orchestration owner is
`TradeLifecycleServiceV2`. This is a canonical candidate, not proof that all
API, CLI, legacy, or parallel execution paths use it exclusively.

### 6.3 Phase 1 requirement disposition

The following remain `PARTIALLY_IMPLEMENTED`:

- `PH1-REQ-001` — repository-derived runtime call graph;
- `PH1-REQ-002` — canonical PAPER execution path;
- `PH1-REQ-003` — execution ownership boundaries;
- `PH1-REQ-004` — risk-authority map;
- `PH1-REQ-005` — account and financial-state ownership;
- `PH1-REQ-006` — fill synchronization contract;
- `PH1-REQ-007` — account-switch containment;
- `PH1-REQ-008` — runtime lifecycle ownership;
- `PH1-REQ-009` — API and dashboard ownership inventory;
- `PH1-REQ-011` — characterization coverage.

No Phase 1 requirement is certified closed by the closure wave.

### 6.4 Phase 1 closure-wave findings

The closure wave does not prove:

- one process-wide canonical runtime owner;
- exclusive use of one canonical PAPER path;
- one risk authority and precedence model for every limit;
- complete cross-subsystem financial synchronization;
- global duplicate-fill and retry idempotency;
- interrupted-fill recovery across all state domains;
- complete account isolation across every caller and projection;
- complete route and authorization inventory;
- WebSocket authorization and account isolation;
- ASGI/CLI runtime equivalence;
- complete compatibility-path safety characterization;
- operational startup-to-PAPER smoke testing.

Phase 1 is not closed and the broader PAPER MVP is not approved.

### 6.5 Phase 1 exit-gate disposition

The closure wave did not satisfy these required gates:

1. One canonical runtime path used by all relevant entry points.
2. Accepted PAPER end-to-end integration evidence across the application boundary.
3. Rejected-signal zero-side-effect evidence across all execution-capable paths.
4. Complete PAPER/LIVE mechanical isolation evidence.
5. One canonical risk-authority and precedence model.
6. Complete cross-subsystem fill synchronization and identity linkage.
7. Global duplicate and restart idempotency evidence.
8. Complete route, account-scope, and authorization inventory.
9. Complete WebSocket authorization and account-isolation evidence.
10. Operational startup-to-PAPER smoke-test evidence.

A green full regression alone does not satisfy these gates.

---

## 7. PHASE 1 EXCLUSIONS

Phase 1 does not include:

- autonomous LIVE trading;
- physical real-money broker submission;
- physical broker OCO or protective-order submission;
- automatic PAPER-to-LIVE conversion;
- destructive architecture consolidation;
- deletion of legacy or duplicate-looking modules;
- TradingView implementation;
- adding new external market-data providers;
- external economic-news ingestion;
- new intelligence or technical-indicator functionality;
- machine learning or adaptive learning;
- general assistant or Jarvis expansion;
- voice, mobile, Telegram, WhatsApp, or email product expansion;
- product, membership, billing, or commercialization work;
- complete dashboard product expansion;
- production deployment;
- production monitoring and alerting;
- changes to credentials, secrets, or deployment security configuration.

Phase 1 may inspect these areas where needed to establish ownership and
boundaries, but implementation remains outside scope.

---

## 8. PHASE 1 ENTRY GATE

Phase 1 entry is satisfied by the supplied evidence:

- Phase 0 remains certified;
- current repository and tests were available;
- application entry points were characterized;
- LIVE and physical broker execution remain disabled;
- no critical safety defect was knowingly bypassed;
- relevant implementation and test files were inspected;
- ambiguity was recorded rather than guessed;
- work remained within reliability, ownership, characterization, and
  documentation scope;
- destructive consolidation was not performed.

Entry certification does not imply Phase 1 completion.

---

## 9. PHASE 1 TEST AND SAFETY GATES

The supplied evidence reports:

```text
BACKEND_TEST_COUNT=630
BACKEND_TESTS_PASSED=5041
BACKEND_TEST_EXIT=0
```

This is supplied current regression evidence, not a test execution performed
during this documentation update. The historical Phase 0 result of
`5082 tests passed` remains limited to Phase 0 certification.

Current characterization supports the following safety boundaries on the
reviewed paths:

- rejected or blocked signals stop before execution side effects;
- risk failures fail closed on characterized paths;
- stale and invalid market data is rejected on characterized paths;
- explicitly supplied quotes are required;
- synthetic spread generation is prohibited;
- PAPER is the only approved execution scope;
- logical protections are not physical broker orders;
- read-side dashboard behavior is observational in characterized routes;
- account switching freezes and retires unsafe source runtimes;
- invalid or incomplete recovery blocks execution;
- autonomous LIVE trading remains blocked.

The following remain Phase 1 test gaps:

- route-to-lifecycle delegation;
- application-wide rejected-signal zero-side-effect coverage;
- parallel-path fail-closed equivalence;
- complete PAPER/LIVE mechanical isolation;
- global duplicate-submission idempotency;
- cross-subsystem fill atomicity;
- ASGI/CLI equivalence;
- complete WebSocket account isolation;
- complete route authorization and account-scope matrix;
- operational startup-to-PAPER smoke testing.

---

## 10. PHASE 1 DELIVERABLES AND EVIDENCE PACKAGE

The closure-wave package contains or identifies:

- runtime call-graph characterization;
- canonical PAPER execution candidate;
- execution ownership characterization;
- risk-authority characterization;
- financial-fill synchronization characterization;
- account-isolation characterization;
- lifecycle and recovery characterization;
- API/dashboard ownership characterization;
- compatibility and supersession register;
- characterization-test gap audit;
- open-risk and unresolved-authority register;
- supplied current regression evidence;
- explicit safety boundaries and limitations;
- explicit closure decision that Phase 1 is not closed.

The package is evidence-complete for characterization and closure-wave review,
but not sufficient for Phase 1 closure or PAPER MVP approval.

---

## 11. FUTURE PHASES

The following phase structure remains planning structure only. Each phase
requires its own entry and exit approval.

### Phase 2 — Data and Market Intelligence

Validated, traceable, freshness-aware market data and intelligence. Do not add
providers or new intelligence functionality during Phase 1.

### Phase 3 — Strategy Validation and Decision Integrity

Canonical signal and trade-plan contracts, decision traceability, reproducible
validation, and strategy-data provenance.

### Phase 4 — Controlled PAPER Execution System

Complete isolated PAPER execution, authorization, idempotency, synchronization,
and recovery.

### Phase 5 — AI, Learning, and Trading Memory

Auditable advisory intelligence, learning provenance, and safe separation from
execution authorization.

### Phase 6 — User Product and Dashboard

A coherent authorized PAPER product surface and route-level read-side safety.

### Phase 7 — Integrations and Operations

Providers, health, observability, backup, deployment, runbooks, and operational
smoke testing.

### Phase 8 — Commercialization

Approved user management, packages, entitlements, and commercial boundaries.

### Phase 9 — Advanced Autonomy

Separately approved autonomy initiatives only. LIVE execution remains blocked
unless a separate authorization and independent safety-validation phase changes
that status.

---

## 12. MVP, BETA, AND PRODUCTION BOUNDARIES

The controlled PAPER MVP is not approved merely because Phase 1 has been
characterized or the closure wave has been reviewed.

MVP approval requires evidence for:

1. One canonical runtime path.
2. Accepted PAPER end-to-end integration.
3. Rejected-signal zero-side-effect integration.
4. PAPER/LIVE isolation.
5. Canonical risk authority.
6. Cross-subsystem fill synchronization.
7. Idempotent duplicate and restart behavior.
8. Recovery-or-block semantics.
9. Complete route and authorization matrix.
10. Current full backend regression.
11. Operational startup-to-PAPER smoke test.

Beta requires an approved MVP, operational monitoring, support procedures,
backup and restore validation, and controlled user scope.

Production Ready means a supportable monitored PAPER product. It does not mean
LIVE trading, autonomous trading, or physical broker submission.

---

## 13. CURRENT NEXT ACTION

Proceed to Phase 2 planning: Data and Market Intelligence; keep LIVE disabled.

### Historical Phase 1 closure sequence

Continue Phase 1 Core Reliability work in this order:

```text
route-to-TradeLifecycleServiceV2 characterization
→ parallel execution-path fail-closed tests
→ PAPER connector isolation and duplicate-submission tests
→ cross-subsystem fill synchronization and failure-injection tests
→ ASGI/CLI equivalence and CLI snapshot handling
→ account-bound auxiliary-store and WebSocket isolation
→ executable route and authorization inventory
→ compatibility-path safety characterization
→ operational startup-to-PAPER smoke testing
```

This action does not authorize:

- production-code expansion outside the approved scope;
- destructive consolidation;
- LIVE execution;
- physical broker submission;
- product expansion.

---

## 14. PERMANENT SAFETY BOUNDARY

ARMS AI must become safer as autonomy increases.

The following remain binding:

- rejected signals cannot execute;
- read-only operations cannot trade;
- risk controls fail closed;
- PAPER and LIVE execution remain separate;
- recovery must reconstruct and validate state or block;
- supplied quotes are required;
- synthetic spreads are prohibited;
- runtime account configuration is authoritative;
- historical evidence is not current implementation proof;
- destructive consolidation requires call-graph and compatibility evidence;
- autonomous LIVE trading remains blocked;
- physical broker OCO and protective-order submission remain unavailable.

# ARMS AI — MASTER ROADMAP

> Evidence-based roadmap for ARMS AI.
> Current repository code and tests are authoritative for implementation status.
> Historical evidence preserves intent and prior demonstrations but does not
> prove current implementation.

---

## 1. ROADMAP STATUS

Current status:

`PHASE 1 CERTIFIED FOR ENTRY-GATE VERIFICATION`

Historical consolidation status:

`COMPLETE — GREEN AUDIT CHAIN 210-290 RECONCILED`

Phase 0 status:

`CLOSED — FORMALLY CERTIFIED`

Phase 1 status:

`DEFINED — CORE RELIABILITY`

The roadmap is now reconciled against:

- `AGENTS.md`
- `HISTORICAL_EVIDENCE_2026.md`
- `CONSOLIDATED_AUDIT_CONTEXT.md`
- current repository implementation and tests
- Phase 0 certified closure
- completed GREEN audits 210 through 290

Phase 1 scope is formally defined, but Phase 1 implementation is not complete.
Certification of Phase 1 scope does not certify that its requirements have been
implemented.

Autonomous LIVE trading remains blocked.

---

## 2. EVIDENCE AND STATUS POLICY

The following evidence hierarchy applies:

1. Current repository implementation and current tests.
2. Current runtime composition and operational evidence.
3. Formal Phase 0 certification.
4. Completed GREEN audit evidence.
5. Historical documentation and historical demonstrations.

A component filename, class name, roadmap statement, historical API response,
or prior test report does not prove current implementation by itself.

Capabilities must be classified using the following statuses:

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

`VERIFIED_CLOSED` is reserved for the formally certified Phase 0 scope unless a
future certification explicitly establishes another closed scope.

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

Phase 0 consisted of eight critical stabilization requirements:

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
- complete cross-subsystem state synchronization;
- complete route or authorization coverage beyond the certified scope.

---

## 5. HISTORICAL CONSOLIDATION AND GREEN AUDIT CHAIN

Status:

`COMPLETE`

GREEN audits 210 through 290 established the following:

- historical requirements were reconciled against current repository evidence;
- current implementation status was separated from historical intent;
- architecture duplication and supersession risks were documented;
- MVP gaps were identified;
- the Requirements Matrix was reconciled;
- Master Memory and Decision Log reconciliation requirements were defined;
- the final roadmap design was completed;
- Phase 1 scope was formally certified;
- no production code or tests were modified by the audit chain;
- autonomous LIVE trading remained disabled;
- no destructive consolidation was authorized.

The audit chain does not itself mark unresolved capabilities as implemented.
Phase 1 requirements remain open until repository-derived characterization,
integration, and operational evidence is produced.

---

## 6. PHASE 1 — CORE RELIABILITY

Status:

`DEFINED — CERTIFIED FOR ENTRY-GATE VERIFICATION`

### 6.1 Objective

Establish a repository-derived authoritative runtime architecture for the
controlled PAPER trading system.

Phase 1 is an architecture, ownership, characterization, and reliability
phase. It does not expand product scope and does not enable LIVE execution.

### 6.2 Scope

Phase 1 covers:

- the repository-derived runtime call graph;
- canonical market-data-to-decision-to-PAPER execution composition;
- execution ownership boundaries;
- risk-authority ownership;
- account and financial-state ownership;
- fill synchronization;
- account-switch containment;
- startup, shutdown, recovery, and pending-operation ownership;
- API and dashboard route ownership;
- compatibility and supersession classification;
- characterization tests;
- the canonical documentation baseline.

### 6.3 Phase 1 requirements

The following requirements are in scope and remain open until verified.

#### PH1-REQ-001 — Repository-derived runtime call graph

Document the active runtime path from the actual process entry point through:

- application factory;
- router composition;
- startup and shutdown;
- runtime context publication;
- market-data intake and validation;
- signal generation;
- decision and admission;
- trade-plan validation;
- risk evaluation;
- PAPER execution;
- position and protection management;
- account and portfolio updates;
- journal and history updates;
- dashboard events;
- persistence;
- recovery;
- pending-operation reconciliation.

The call graph must distinguish active, parallel, compatibility, legacy, and
unverified paths.

#### PH1-REQ-002 — Canonical PAPER execution path

Select and document one canonical path:

```text
validated market data
→ market context and intelligence
→ signal or decision
→ admission and risk validation
→ validated trade plan
→ explicit PAPER authorization
→ PAPER execution
→ simulated fill
→ position and protection updates
→ account, portfolio, journal, and history updates
→ dashboard event publication
→ durable persistence
→ recovery and semantic validation
```

No canonical stage may bypass freshness, account, authorization, risk, or state
controls.

#### PH1-REQ-003 — Execution ownership boundaries

Identify responsibility and call direction for:

- signal admission;
- trade-plan validation;
- order preparation;
- execution orchestration;
- PAPER connector or simulator invocation;
- fill handling;
- position lifecycle;
- logical OCO and protective-order state;
- break-even;
- trailing stops;
- partial take profit;
- execution persistence;
- execution recovery.

No retained component may provide an unclassified alternative execution path
that bypasses canonical admission or risk controls.

#### PH1-REQ-004 — Risk-authority map

Identify one authoritative source, or explicitly record unresolved ownership,
for:

- daily loss;
- maximum drawdown;
- trading-block state;
- contract limits;
- position sizing;
- exposure limits;
- account restrictions;
- market freshness;
- economic-news restrictions;
- stop-loss and trade-plan requirements;
- execution authorization.

Consumers must not silently replace, weaken, or default these authorities.

#### PH1-REQ-005 — Account and financial-state ownership

Define ownership and update direction for:

- balance and equity;
- daily PnL;
- realized and unrealized PnL;
- drawdown;
- open positions;
- portfolio exposure;
- journal records;
- trade history;
- signal history;
- protection state;
- dashboard projections.

Reporting and analytics components must derive data from canonical state rather
than maintain competing financial authorities.

#### PH1-REQ-006 — Fill synchronization contract

Define the event and update contract for a PAPER fill, including:

- signal identity;
- trade-plan identity;
- execution-request identity;
- fill identity;
- account scope;
- idempotent application;
- position linkage;
- portfolio linkage;
- account-state linkage;
- journal and history linkage;
- protection and OCO linkage;
- dashboard-event linkage;
- persistence linkage;
- failure and recovery behavior.

The contract must define duplicate, rejected, partial, interrupted, and retried
operation semantics.

#### PH1-REQ-007 — Account-switch containment

Verify and document that account switching cannot leak:

- positions;
- risk state;
- pending operations;
- runtime services;
- dashboard events;
- journal or history state;
- credentials;
- account-scoped configuration.

The active account boundary must be preserved across every account-bound service.

#### PH1-REQ-008 — Runtime lifecycle ownership

Identify authoritative ownership for:

- clean startup;
- snapshot loading;
- recovery;
- semantic validation;
- pending-operation reconciliation;
- runtime readiness;
- graceful shutdown;
- failure transitions;
- blocked-state transitions.

Layered lifecycle services may remain, but their ownership and call direction
must be explicit.

Recovery success must mean that required operational state was reconstructed
and validated.

#### PH1-REQ-009 — API and dashboard ownership inventory

Create an inventory of:

- application routes;
- router loaders;
- mutating endpoints;
- read-only endpoints;
- dashboard routes;
- widget and refresh routes;
- WebSocket connections and subscriptions;
- account-scoped operations;
- authorization dependencies.

For every operation, document:

- protocol and method;
- mutating or read-only classification;
- required authorization;
- account scope;
- service owner;
- execution reachability;
- relevant tests.

#### PH1-REQ-010 — Compatibility and supersession register

Classify duplicate-looking components as appropriate:

- active;
- compatibility-required;
- legacy;
- likely superseded;
- parallel with distinct responsibilities;
- needs verification;
- blocked;
- duplicate;
- conflicting.

Do not delete, merge, or declare modules superseded solely from filenames or
version numbers.

#### PH1-REQ-011 — Characterization coverage

Add or identify characterization tests for retained paths that may affect:

- admission;
- risk evaluation;
- position sizing;
- PAPER/LIVE selection;
- position creation;
- portfolio mutation;
- account mutation;
- journal and history writes;
- protection and OCO state;
- dashboard event publication;
- persistence;
- recovery;
- account switching;
- read-only API behavior.

#### PH1-REQ-012 — Canonical documentation baseline

Produce and maintain:

- runtime call-graph inventory;
- canonical PAPER execution-path document;
- execution ownership map;
- risk-authority map;
- financial-state ownership map;
- recovery ownership map;
- API and dashboard route inventory;
- compatibility and supersession register;
- characterization-test inventory;
- open-risk and unresolved-authority register.

Documentation must preserve evidence boundaries and must not claim capabilities
are implemented solely because files or historical reports exist.

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
- new intelligence functionality;
- new technical-indicator functionality;
- machine learning;
- adaptive learning;
- general assistant or Jarvis expansion;
- voice, mobile, Telegram, WhatsApp, or email product expansion;
- product, membership, billing, or commercialization work;
- complete dashboard product expansion;
- production deployment;
- production monitoring and alerting;
- strategy certification beyond characterization of existing paths;
- changes to credentials, secrets, or deployment security configuration.

Phase 1 may inspect these areas where needed to establish ownership and
boundaries, but implementation remains outside scope.

---

## 8. PHASE 1 ENTRY GATE

Phase 1 may begin only when:

1. Phase 0 remains formally certified closed.
2. All eight Phase 0 requirements retain `VERIFIED_CLOSED`.
3. Current repository code and current tests are available.
4. The actual application entry point is identified or explicitly recorded as
   unresolved.
5. Autonomous LIVE trading remains disabled.
6. Physical real-money broker submission remains unavailable.
7. No known critical safety defect is knowingly bypassed.
8. Existing user changes and unrelated work are preserved.
9. Relevant implementation and test files have been inspected.
10. Ambiguity affecting execution, risk, account state, or recovery is recorded
    rather than guessed.
11. Work remains limited to reliability, ownership, call-graph,
    characterization, and documentation outcomes.
12. No destructive consolidation is authorized.

---

## 9. PHASE 1 EXIT GATE

Phase 1 is complete only when:

1. The application entry point and startup path are documented.
2. The active runtime call graph is documented through PAPER execution and
   recovery.
3. One canonical PAPER runtime path is selected and documented.
4. Every canonical stage has an identified owner and input/output boundary.
5. Admission, preparation, execution, and state mutation responsibilities are
   separated.
6. Each risk and financial-state authority is identified, or unresolved
   conflicts are explicitly recorded as `NEEDS_VERIFICATION`.
7. Account-switch containment is documented and characterized.
8. Startup, shutdown, recovery, and pending-operation ownership is documented.
9. Recovery success and blocked-state semantics are explicit.
10. The current API and dashboard route inventory is complete for the reviewed
    repository scope.
11. Read-only behavior is mapped and covered by tests.
12. Mutating operations have documented authorization and account scope.
13. PAPER execution is shown to be isolated from LIVE broker paths.
14. Duplicate-looking components are classified without unsupported deletion or
    supersession claims.
15. Characterization tests cover retained paths affecting execution or
    financial state.
16. Open risks and evidence limitations are recorded.
17. No deliverable claims that the broader PAPER MVP is approved.
18. Autonomous LIVE trading remains blocked.
19. No critical safety regression is introduced.
20. The evidence package is reviewed against the Requirements Matrix, Decision
    Log, Master Memory, and `AGENTS.md`.

---

## 10. PHASE 1 TEST GATE

Current repository-derived test evidence is required. Historical test results do
not satisfy this gate.

Required tests must cover:

1. Rejected or blocked signals produce zero execution side effects.
2. Stale or invalid market input cannot reach execution.
3. Unauthorized execution cannot reach PAPER execution.
4. PAPER mode cannot select or invoke a LIVE connector.
5. Valid admitted PAPER requests follow the canonical path.
6. Duplicate requests follow the defined idempotency contract.
7. Fill updates preserve signal, plan, fill, position, account, portfolio,
   journal, history, protection, event, and persistence linkage.
8. Interrupted or failed operations recover or enter a blocked state.
9. Repeated recovery does not duplicate fills or state mutations.
10. Account switching does not leak account-scoped state or events.
11. Dashboard reads, reports, widgets, refreshes, health checks, and WebSocket
    subscriptions do not execute trades.
12. Privileged and mutating routes enforce authorization and account scope.
13. Missing, stale, inconsistent, or invalid risk data fails closed.
14. Conflicting ownership dependencies are surfaced rather than silently
    defaulted.
15. Compatibility paths preserve tested public and persisted-state behavior.

The current full backend regression must be run for release-quality claims. The
historical `5082 tests passed` result remains Phase 0 certification evidence and
must not be presented as the current full-suite result without rerunning it.

---

## 11. PHASE 1 SAFETY GATE

Phase 1 cannot pass unless all of the following remain true:

- `accepted: false` is an absolute execution boundary;
- rejected, blocked, stale, invalid, incomplete, unsafe, and unauthorized
  signals produce zero execution side effects;
- fail-closed risk behavior is preserved;
- market freshness and quote authority remain enforced;
- bid/ask quotes and spreads are never manufactured;
- PAPER execution cannot reach a LIVE or real-money broker;
- read-only operations cannot create execution effects;
- account switching cannot leak execution or risk state;
- recovery cannot report success before required state is reconstructed and
  validated;
- failed recovery enters a blocked, non-executing state;
- physical broker OCO and protective-order submission remain unavailable;
- historical evidence is not used as current implementation proof;
- no activity weakens authorization, account isolation, risk controls, or
  persistence guarantees;
- no autonomous LIVE capability is introduced or enabled.

Any violation is a critical Phase 1 blocker.

---

## 12. PHASE 1 DELIVERABLES

The Phase 1 evidence package must contain:

- runtime call-graph inventory;
- canonical PAPER execution path;
- execution ownership map;
- risk-authority map;
- financial-state ownership map;
- recovery ownership map;
- API and dashboard route inventory;
- compatibility and supersession register;
- characterization-test inventory;
- open-risk register;
- unresolved-authority register;
- current test results;
- safety-gate results;
- limitations and evidence boundaries.

---

## 13. FUTURE PHASES

The following phase structure remains approved as planning structure only.
Each phase requires its own entry and exit approval.

### Phase 2 — Data and Market Intelligence

Focus on validated, traceable, freshness-aware market data and intelligence.
Do not add providers or intelligence functionality during Phase 1.

### Phase 3 — Strategy Validation and Decision Integrity

Focus on canonical signal and trade-plan contracts, decision traceability,
reproducible validation, and strategy-data provenance.

### Phase 4 — Controlled PAPER Execution System

Focus on complete isolated PAPER execution, authorization, idempotency,
synchronization, and recovery.

### Phase 5 — AI, Learning, and Trading Memory

Focus on auditable advisory intelligence, learning provenance, and safe
separation from execution authorization.

### Phase 6 — User Product and Dashboard

Focus on a coherent authorized PAPER product surface and route-level
read-side safety.

### Phase 7 — Integrations and Operations

Focus on providers, health, observability, backup, deployment, runbooks, and
operational smoke testing.

### Phase 8 — Commercialization

Focus on approved user management, packages, entitlements, and commercial
boundaries.

### Phase 9 — Advanced Autonomy

Focus only on separately approved autonomy initiatives. LIVE execution remains
blocked unless a separate authorization and independent safety-validation phase
changes that status.

---

## 14. MVP, BETA, AND PRODUCTION BOUNDARIES

The controlled PAPER MVP is not approved merely because Phase 1 is defined.

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

MVP, Beta, and Production Ready remain separate approval boundaries.

---

## 15. CURRENT NEXT ACTION

Proceed with:

```text
Phase 1 entry-gate verification
→ repository/runtime characterization
→ runtime call-graph inventory
→ canonical ownership maps
→ characterization-test inventory
→ Phase 1 evidence-package review
```

The next action is not product expansion and does not authorize destructive
consolidation or LIVE execution.

---

## 16. SAFETY BOUNDARY

ARMS AI must become safer as autonomy increases.

The following remain permanently applicable:

- rejected signals cannot execute;
- read-only operations cannot trade;
- risk controls fail closed;
- PAPER and LIVE execution remain separate;
- recovery must reconstruct and validate state or block;
- supplied quotes are required;
- synthetic spreads are prohibited;
- runtime account configuration is authoritative;
- historical evidence is not current implementation proof;
- no destructive consolidation occurs without call-graph and compatibility
  evidence;
- autonomous LIVE trading remains blocked.

# ARMS AI — REQUIREMENTS MATRIX

> Evidence-based matrix connecting historical requirements to current repository
> status, certified closure, Phase 1 closure-wave evidence, and approved future
> scope.

---

## STATUS LEGEND

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

`PARTIAL` is normalized to `PARTIALLY_IMPLEMENTED`.

`VERIFIED_CLOSED` is reserved for formally certified closure, currently the
defined Phase 0 scope.

---

## EVIDENCE POLICY

Current repository code, current tests, runtime characterization, current
operational evidence, and the Phase 1 closure-wave evidence are authoritative
for their demonstrated scope.

Historical evidence establishes prior intent, discussion, reported behavior, or
historical demonstrations only.

A requirement must not be marked `VERIFIED_IMPLEMENTED` solely because:

- a file exists;
- a class exists;
- a historical API demonstration exists;
- a roadmap says it exists;
- a prior test count is reported;
- an interface exists without behavior and integration evidence.

The documented Phase 0 result of `5082 tests passed` is Phase 0 certification
evidence. The supplied Phase 1 regression result is:

```text
BACKEND_TEST_COUNT=630
BACKEND_TESTS_PASSED=5041
BACKEND_TEST_EXIT=0
```

That result is supplied repository evidence and was not executed by this
documentation update.

---

## HISTORICAL CONSOLIDATION STATUS

Status:

`COMPLETE — GREEN AUDIT CHAIN 210-290 RECONCILED`

The audit and characterization chain completed:

- capability mapping;
- historical-requirements reconciliation;
- architecture duplication audit;
- MVP gap analysis;
- Requirements Matrix reconciliation;
- Master Memory reconciliation;
- Decision Log reconciliation;
- final roadmap design;
- Phase 1 scope certification;
- Phase 1 runtime, risk, recovery, financial-state, account-isolation,
  API/dashboard, compatibility, and closure-wave characterization.

No production code or tests were modified by this documentation and evidence
work.

---

## PHASE 0 CERTIFICATION

Phase 0 — Critical Stabilization is formally closed.

Certification evidence:

- `PHASE0_REQUIREMENTS=8`
- `PHASE0_VERIFIED_CLOSED=8`
- `PHASE0_PARTIAL_COUNT=0`
- `PHASE0_OPEN_COUNT=0`
- `PHASE0_NEEDS_VERIFICATION_COUNT=0`
- `PHASE0_AUDIT_COMPLETE=YES`
- `PHASE0_CLOSE_RECOMMENDATION=CLOSE`
- documented full backend regression: `5082 tests passed`
- closure commit:
  `c13cd54d7ec0453c86e934ce117ce11764de5a4e`
- closure message:
  `test: close Phase 0 critical stabilization gaps`

The eight certified requirements are:

1. Prevent blocked signals from executing.
2. Remove execution side effects from dashboard read operations.
3. Correct daily PnL synchronization.
4. Correct daily loss and trading-block synchronization.
5. Correct account switching consistency.
6. Complete execution state recovery within the certified scope.
7. Resolve startup/runtime path inconsistencies within the certified scope.
8. Review and enforce API security boundaries within the certified scope.

Phase 0 does not certify Phase 1, the PAPER MVP, production readiness, or LIVE
execution.

---

## PHASE 1 STATUS

Phase 1 is defined as:

`CORE RELIABILITY`

Current status:

`CHARACTERIZED — CLOSURE WAVE REVIEWED — NOT CERTIFIED COMPLETE`

Closure-wave evidence:

```text
PHASE1_VERIFIED_COUNT=2
PHASE1_PARTIAL_COUNT=10
PHASE1_OPEN_COUNT=0
PHASE1_NEEDS_VERIFICATION_COUNT=0
BACKEND_TEST_COUNT=630
BACKEND_TESTS_PASSED=5041
BACKEND_TEST_EXIT=0
```

The full regression is green based on supplied repository evidence. The closure
wave does not close Phase 1 because ten requirements remain partially verified
and the application-wide exit gates are not satisfied.

---

## PHASE 1 REQUIREMENTS

| ID | Parent | Area | Requirement | Evidence Basis | Status | Priority | Acceptance Criteria | Known Limitations |
|---|---|---|---|---|---|---|---|---|
| PH1-REQ-001 | Phase 1 | Runtime | Produce a repository-derived runtime call graph from process entry through startup, routes, market data, decisions, admission, PAPER execution, state updates, persistence, and recovery | Runtime characterization and closure-wave review | PARTIALLY_IMPLEMENTED | P0 | Active entry points, callers, ownership, and recovery path are documented | ASGI, direct factory, CLI, and alternate paths are not proven to share one process-wide owner |
| PH1-REQ-002 | Phase 1 | Execution | Select and document one canonical validated-market-data-to-PAPER-execution path | PAPER call-graph characterization and closure-wave review | PARTIALLY_IMPLEMENTED | P0 | One strongest path is documented and its controls are identified | Exclusive use by every API, CLI, legacy, and parallel path is unproven |
| PH1-REQ-003 | Phase 1 | Execution | Define execution ownership boundaries for admission, validation, preparation, orchestration, PAPER submission, fill handling, position lifecycle, protection, persistence, and recovery | PAPER call graph and compatibility register | PARTIALLY_IMPLEMENTED | P0 | Each stage has one owner or an explicitly documented layered relationship | Parallel execution abstractions remain unresolved |
| PH1-REQ-004 | Phase 1 | Risk | Identify one authoritative source for each risk limit and record unresolved conflicts | Risk-authority characterization | PARTIALLY_IMPLEMENTED | P0 | Daily loss, drawdown, blocks, limits, sizing, exposure, news, freshness, and authorization authorities are mapped | Single authority and precedence are not proven for all limits or paths |
| PH1-REQ-005 | Phase 1 | State | Define account and financial-state ownership for balances, PnL, drawdown, positions, exposure, journal, histories, protections, and dashboard projections | Financial-fill synchronization characterization | PARTIALLY_IMPLEMENTED | P0 | Canonical state owners and update direction are documented | Complete atomic cross-subsystem ownership and synchronization are unproven |
| PH1-REQ-006 | Phase 1 | State | Define an idempotent fill synchronization contract linking signal, plan, request, fill, position, account, portfolio, journal, history, protection, events, persistence, and recovery | Financial-fill synchronization characterization | PARTIALLY_IMPLEMENTED | P0 | Accepted, rejected, duplicate, partial, interrupted, and retried operations have observable semantics | Global idempotency, atomicity, and interrupted-fill recovery remain open |
| PH1-REQ-007 | Phase 1 | Accounts | Verify account-switch containment across positions, risk, pending operations, services, events, journal/history, credentials, and configuration | Account-isolation characterization | PARTIALLY_IMPLEMENTED | P0 | Characterization tests show no cross-account leakage | CLI, legacy, auxiliary-store, dashboard, WebSocket, and every direct-caller path are not fully proven |
| PH1-REQ-008 | Phase 1 | Runtime | Identify authoritative startup, shutdown, recovery, semantic-validation, pending-operation, readiness, failure, and blocked-state ownership | Recovery-lifecycle characterization | PARTIALLY_IMPLEMENTED | P0 | One owner or explicit layer relationship is documented; recovery success means validated state | ASGI/CLI equivalence and complete pending-operation integration remain unresolved |
| PH1-REQ-009 | Phase 1 | API / Dashboard | Inventory routes, widgets, refreshes, reports, WebSockets, account scope, authorization, service ownership, and execution reachability | API/dashboard ownership characterization | PARTIALLY_IMPLEMENTED | P0 | Reviewed routes are classified as read, administrative mutation, or execution-capable mutation | Complete route inventory, account scope, and WebSocket authorization remain open |
| PH1-REQ-010 | Phase 1 | Architecture | Create a compatibility and supersession register for active, parallel, compatibility, legacy, likely superseded, duplicate, conflicting, and unverified modules | Compatibility and supersession register | VERIFIED_IMPLEMENTED | P1 | Retained duplicate-looking paths have evidence-based classifications | Classification does not authorize deletion, merging, or destructive consolidation |
| PH1-REQ-011 | Phase 1 | Testing | Add or identify characterization coverage for all retained paths affecting admission, risk, execution, state, protection, events, persistence, recovery, account switching, and reads | Characterization test-gap audit and closure-wave review | PARTIALLY_IMPLEMENTED | P0 | Current tests verify behavior and relevant side effects on characterized paths | Cross-path equivalence, route delegation, global idempotency, WebSocket isolation, and operational tests remain open |
| PH1-REQ-012 | Phase 1 | Documentation | Produce the canonical runtime, ownership, route, compatibility, characterization, and open-risk documentation baseline | Phase 1 documentation baseline | VERIFIED_IMPLEMENTED | P1 | Evidence package is reviewed against AGENTS.md, the matrix, memory, and decision log | Documentation records unresolved gaps and does not close Phase 1 or approve the PAPER MVP |

### Phase 1 interpretation

`VERIFIED_IMPLEMENTED` for `PH1-REQ-010` and `PH1-REQ-012` means that the
requested register and documentation baseline are present and evidence-based.
It does not mean that all runtime behavior they describe is complete.

The ten `PARTIALLY_IMPLEMENTED` requirements remain partially verified after the
closure wave. No Phase 1 requirement is `VERIFIED_CLOSED`.

---

## CORE SAFETY REQUIREMENTS

| ID | Area | Requirement | Current Evidence | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| SAFE-001 | Execution | Rejected, blocked, stale, invalid, incomplete, unsafe, or unauthorized signals produce zero execution side effects | Phase 0 certification; lifecycle and admission tests; execution characterization | VERIFIED_CLOSED within certified Phase 0 scope; broader paths PARTIALLY_IMPLEMENTED | CRITICAL | Applies to every entry point; broader API, CLI, and legacy coverage remains open |
| SAFE-002 | API / Dashboard | Read-only API, dashboard, analytics, report, widget, refresh, health, and WebSocket operations are non-mutating | Phase 0 dashboard closure; read-side and API/dashboard characterization | VERIFIED_CLOSED within certified Phase 0 scope; broader route coverage PARTIALLY_IMPLEMENTED | CRITICAL | Read operations must not trade |
| SAFE-003 | Risk | Missing, stale, inconsistent, invalid, or unauthorized risk data fails closed | Policy, risk architecture, focused tests, risk characterization | VERIFIED_CLOSED | CRITICAL | Cross-path risk authority certified fail closed; final confluence, Probability V2, and Execution V2 consume resolved runtime authority; early confluence is explicitly non-final and characterization-guarded |
| SAFE-004 | Execution | PAPER execution cannot select or reach a LIVE or real-money broker | PAPER components, account isolation, policy, compatibility characterization; runtime PAPER chain and connector boundary certification | VERIFIED_CLOSED | CRITICAL | PAPER lifecycle is mechanically bound to PaperBrokerConnectorV2 and PaperExecutionEngineV2; invalid connector/engine injection fails closed; LIVE and physical real-money execution remain blocked |
| SAFE-005 | Recovery | Recovery reconstructs and validates required state or enters a blocked non-executing state | Phase 0 recovery certification; recovery services and tests | VERIFIED_CLOSED within certified scope; broader cross-subsystem behavior PARTIALLY_IMPLEMENTED | CRITICAL | No false recovery success |
| SAFE-006 | Market Data | Explicitly supplied quotes are required; synthetic bid/ask or spread generation is prohibited | Runtime quote authority and tests | VERIFIED_IMPLEMENTED | CRITICAL | Synthetic spread generation is superseded |
| SAFE-007 | Accounts | Runtime account configuration is authoritative | Account configuration and account-isolation characterization | VERIFIED_IMPLEMENTED | HIGH | Historical account examples are not defaults |
| SAFE-008 | Architecture | No destructive consolidation occurs without runtime call-graph and compatibility evidence | GREEN audit 230; Decision Log DEC-0011 | VERIFIED_CLOSED as a governing decision | HIGH | Applies before deletion or merging |

---

## CURRENT CAPABILITY REQUIREMENTS

| ID | Area | Requirement | Current Evidence | Status | Priority | Notes |
|---|---|---|---|---|---|---|
| DATA-001 | Market Data | Validate supplied symbol, timestamp, and numeric market values | Price-feed and market-data components/tests | VERIFIED_IMPLEMENTED | P1 | Scope of all malformed-data paths requires continued verification |
| DATA-002 | Market Data | Reject stale market data before admission or execution | Freshness, quote-authority, and admission tests | VERIFIED_IMPLEMENTED for tested paths | P0 | Broader integration remains open |
| DATA-003 | Market Data | Use one authoritative runtime quote source | Quote-authority components and characterization | PARTIALLY_IMPLEMENTED | P0 | Complete runtime composition is unresolved |
| DATA-004 | Market Data | Do not manufacture bid/ask quotes or spreads | Runtime quote authority and tests | VERIFIED_IMPLEMENTED | CRITICAL | Supersedes synthetic spread assumptions |
| DATA-005 | Market Data | Reject missing, malformed, conflicting, duplicate, or out-of-order required data | Market-data characterization and audit evidence | NEEDS_VERIFICATION | P1 | Complete behavior coverage is not established |
| DATA-006 | Market Data | Provide a concrete external market-data provider boundary | No complete provider evidence | NEEDS_VERIFICATION | P1 | Outside Phase 1 |
| INTEL-001 | Intelligence | Provide market-state storage and retrieval | Market-state engine and tests | VERIFIED_IMPLEMENTED | P1 | Component-level status |
| INTEL-002 | Intelligence | Provide market-structure analysis | Market-structure engine | VERIFIED_IMPLEMENTED | P1 | Complete historical breadth remains open |
| INTEL-003 | Intelligence | Provide trend, context, and regime analysis | Current engines and tests | VERIFIED_IMPLEMENTED | P1 | Runtime composition remains subject to characterization |
| INTEL-004 | Intelligence | Provide confluence scoring | Confluence engine and tests | VERIFIED_IMPLEMENTED | P1 | End-to-end integration remains open |
| INTEL-005 | Intelligence | Provide probability and confidence behavior | Probability and confidence components | NEEDS_VERIFICATION | P1 | Runtime integration is not proven |
| INTEL-006 | Intelligence | Provide multi-timeframe decision analysis | Multi-timeframe engine and test | VERIFIED_IMPLEMENTED at component level | P1 | Canonical runtime use remains open |
| INTEL-007 | Intelligence | Fail closed when required intelligence inputs are missing or invalid | Policy and audit requirements | NEEDS_VERIFICATION | P0 | Requires integration tests |
| SIGNAL-001 | Decision | Generate traceable signals with identity, timestamps, account context, and source data | Signal and decision components | PARTIALLY_IMPLEMENTED | P0 | Complete contract remains open |
| SIGNAL-002 | Decision | Include validated entry, stop, target, quantity, risk/reward, admission, and rejection reasons | Trade-plan and decision components | PARTIALLY_IMPLEMENTED | P0 | Contract and immutability remain open |
| SIGNAL-003 | Decision | Prevent mutation of an admitted trade plan | Audit requirement | NEEDS_VERIFICATION | P0 | Requires characterization test |
| RISK-001 | Risk | Support account-specific risk profiles | Account and funding-firm components | VERIFIED_IMPLEMENTED | HIGH | Runtime authority mapping remains open |
| RISK-002 | Risk | Enforce daily loss and synchronize daily PnL/trading-block state | Phase 0 evidence and tests | VERIFIED_CLOSED within certified scope | CRITICAL | Certified scope limitation applies |
| RISK-003 | Risk | Enforce maximum drawdown | Account and risk components | PARTIALLY_IMPLEMENTED | P0 | Complete end-to-end enforcement is not established |
| RISK-004 | Risk | Enforce contract limits and position sizing | Profiles, instruments, sizing, and tests | VERIFIED_IMPLEMENTED | HIGH | Multiple authorities require mapping |
| RISK-005 | Risk | Enforce exposure and portfolio risk limits | Exposure and portfolio-risk components | PARTIALLY_IMPLEMENTED | P0 | Integrated enforcement remains open |
| EXEC-001 | Execution | Convert admitted signals into prepared orders | Execution manager and tests | VERIFIED_IMPLEMENTED | HIGH | Canonical path remains open |
| EXEC-002 | Execution | Stop rejected signals before executable preparation and side effects | Phase 0 closure and execution tests | VERIFIED_CLOSED within certified scope | CRITICAL | Broader entry-point proof remains open |
| EXEC-003 | Execution | Execute accepted orders through an explicit PAPER-only path | PAPER engine, connector, and tests | VERIFIED_IMPLEMENTED at component level | P0 | Isolation proof remains open |
| EXEC-004 | Execution | Simulate fills and record slippage transparently | PAPER execution evidence | VERIFIED_IMPLEMENTED | HIGH | End-to-end linkage remains open |
| EXEC-005 | Execution | Prevent duplicate submissions from producing duplicate fills | Closure-wave gap review | NEEDS_VERIFICATION | P0 | Cross-entry-point idempotency is missing |
| EXEC-006 | Execution | Maintain logical OCO and protective-order state without physical broker submission | OCO and protection components/tests | VERIFIED_IMPLEMENTED | HIGH | Physical submission remains unavailable |
| EXEC-007 | Execution | Keep autonomous LIVE trading and physical real-money submission disabled | Policy and Decision Log | BLOCKED | CRITICAL | Separate future authorization required |
| STATE-001 | State | Maintain durable account state | Account manager and tests | VERIFIED_IMPLEMENTED | HIGH | Broader synchronization remains open |
| STATE-002 | State | Maintain portfolio positions and analytics | Portfolio components and tests | VERIFIED_IMPLEMENTED | HIGH | Canonical financial authority remains open |
| STATE-003 | State | Maintain trade and signal history | History stores and tests | VERIFIED_IMPLEMENTED | HIGH | Cross-linkage remains open |
| STATE-004 | State | Maintain a durable trade journal | Journal component and lifecycle characterization | PARTIALLY_IMPLEMENTED | P0 | Persistence and recovery guarantees remain open |
| STATE-005 | State | Establish one authoritative financial-state source | Financial synchronization characterization | NEEDS_VERIFICATION | P0 | Portfolio/account direction is known; complete authority remains open |
| STATE-006 | State | Apply fill, position, account, portfolio, journal, history, protection, event, and persistence updates consistently | Lifecycle and state characterization | NEEDS_VERIFICATION | P0 | Atomicity and all-path consistency remain open |
| STATE-007 | State | Make fill application idempotent and recoverable | Recovery, lifecycle, and characterization evidence | NEEDS_VERIFICATION | P0 | Global duplicate and interruption behavior remain open |
| REC-001 | Recovery | Capture and persist execution state | Execution state components/tests | VERIFIED_IMPLEMENTED | HIGH | Certified scope is narrower than full system recovery |
| REC-002 | Recovery | Restore and semantically validate execution state | Recovery components/tests and Phase 0 | VERIFIED_CLOSED within certified scope | CRITICAL | Broader subsystem recovery remains open |
| REC-003 | Recovery | Reconcile pending operations | Reconciliation component/tests and lifecycle characterization | PARTIALLY_IMPLEMENTED | P0 | Complete startup-path integration remains open |
| REC-004 | Recovery | Recover or block when state is incomplete or inconsistent | Policy and recovery evidence | VERIFIED_IMPLEMENTED for covered paths | CRITICAL | Full coverage remains open |
| API-001 | API | Provide application factory and configuration validation | API factory and configuration components | VERIFIED_IMPLEMENTED | HIGH | Full import/runtime composition requires continued characterization |
| API-002 | API | Inventory and register current routes | Application, router loader, routers, and API characterization | PARTIALLY_IMPLEMENTED | P0 | Reviewed inventory exists; complete inventory remains open |
| API-003 | API | Enforce authorization and account scope on privileged/mutating routes | Authorization components, route characterization, and tests | PARTIALLY_IMPLEMENTED | P0 | Complete route matrix remains open |
| API-004 | API | Keep read operations non-mutating | Phase 0 evidence, read-side tests, and API characterization | VERIFIED_CLOSED within certified scope; broader route coverage PARTIALLY_IMPLEMENTED | CRITICAL | Route-by-route verification remains open |
| API-005 | API | Keep WebSocket subscriptions authorized and non-mutating | Dashboard/WebSocket components and tests | NEEDS_VERIFICATION | P0 | Account isolation and complete authorization remain open |
| API-006 | Dashboard | Publish dashboard events without execution side effects | Dashboard event components and characterization | PARTIALLY_IMPLEMENTED | P1 | Ordering, deduplication, and account isolation remain open |
| VALID-001 | Validation | Validate historical OHLC input and deterministic replay | Backtesting schemas and replay tests | VERIFIED_IMPLEMENTED | P1 | Dataset provenance remains open |
| VALID-002 | Validation | Run backtests and persist job lifecycle state | Backtesting runners, jobs, and tests | VERIFIED_IMPLEMENTED | P1 | Full production traceability remains open |
| VALID-003 | Validation | Provide walk-forward, Monte Carlo, scoring, grading, and certification infrastructure | Backtesting components and tests | VERIFIED_IMPLEMENTED | P1 | Infrastructure does not prove strategy validity |
| VALID-004 | Validation | Preserve dataset and strategy traceability and prevent silent substitution | Audit requirement | PARTIALLY_IMPLEMENTED | P1 | Negative tests remain needed |
| AI-001 | AI | Define AI provider response contract | Provider base contract | VERIFIED_IMPLEMENTED | P2 | Interface does not prove provider integration |
| AI-002 | AI | Provide concrete external AI providers | No complete evidence | NEEDS_VERIFICATION | P2 | Outside Phase 1 |
| AI-003 | AI | Provide trading-memory and outcome-learning behavior | Memory and learning components | PARTIALLY_IMPLEMENTED | P2 | Persistence and adaptive behavior remain open |
| PROD-001 | Product | Provide a complete dashboard product surface | Frontend and dashboard components | PARTIALLY_IMPLEMENTED | P2 | Outside Phase 1 |
| PROD-002 | Product | Provide mobile, commercial, membership, and general assistant surfaces | Historical evidence only | HISTORICAL_IDEA / DEFERRED | P2 | Outside current controlled scope |
| OPS-001 | Operations | Provide startup, readiness, monitoring, backup, restore, and runbook support | Runtime components exist; complete operational evidence absent | NEEDS_VERIFICATION | P1 | Outside Phase 1 implementation scope |

---

## HISTORICAL-ONLY REQUIREMENTS

The following remain preserved as historical ideas unless separately promoted:

- broad assistant platform;
- exact historical 15m/5m/1m workflow;
- historical NQ BUY and confidence/A+ demonstrations;
- historical PAPER fill demonstrations;
- Topstep 150K example limits;
- Telegram;
- WhatsApp;
- mobile;
- voice assistant;
- general Jarvis assistant;
- Home Assistant extensions;
- facial recognition and robotics;
- memberships and commercial packages;
- commercial signal distribution;
- historical pricing;
- historical completion estimates.

Historical API demonstrations are evidence of prior discussion or reported
behavior only.

---

## DEFERRED REQUIREMENTS

The following are deferred from the current controlled PAPER and Phase 1 scope:

- TradingView integration;
- additional external market-data providers;
- external economic-news ingestion;
- machine learning;
- adaptive learning;
- persistent general-assistant memory;
- voice, mobile, Telegram, WhatsApp, and email product expansion;
- memberships and commercialization;
- Home Assistant integrations;
- production deployment;
- production-grade monitoring;
- physical broker OCO and protective-order submission.

---

## BLOCKED REQUIREMENTS

The following remain blocked:

- autonomous LIVE trading;
- unvalidated real-money broker execution;
- physical real-money broker submission;
- automatic PAPER-to-LIVE conversion;
- any execution path bypassing risk, authorization, freshness, account, or
  recovery controls.

---

## SUPERSEDED, DUPLICATE, AND CONFLICTING REQUIREMENTS

| Classification | Requirement | Resolution |
|---|---|---|
| SUPERSEDED | Synthetic bid/ask or spread generation | Explicitly supplied quotes are required |
| SUPERSEDED | Historical account values as universal defaults | Runtime account configuration is authoritative |
| DUPLICATE | Repeated Phase 0 closure rows across documents | Retain traceability but use the eight canonical Phase 0 IDs |
| DUPLICATE | Generic pending historical consolidation row `REQ-001` | Treat as documentation tracking, not an independent product requirement |
| CONFLICT | Historical LIVE vision versus current safety policy | Preserve history; keep LIVE blocked |
| CONFLICT | Historical API demonstrations versus current implementation proof | Preserve demonstrations; require current code and tests |
| NEEDS_VERIFICATION | Duplicate-looking execution, risk, runtime, intelligence, dashboard, and recovery modules | Characterize call graph and compatibility before consolidation |

---

## PHASE 1 TRACEABILITY AND ACCEPTANCE POLICY

Phase 1 requirements are scope-certified and characterized, not phase-closed.

A Phase 1 requirement may be promoted only when evidence includes, as
appropriate:

- exact implementation files;
- exact current tests;
- test functions or classes;
- call-graph evidence;
- side-effect observations;
- current verification date;
- known limitations;
- account and authorization scope;
- parent requirement or Phase 0 relationship.

Evidence categories:

- `CODE`
- `TEST`
- `INTEGRATION_TEST`
- `PHASE0_CERTIFICATION`
- `HISTORICAL_EVIDENCE`
- `DOCUMENTATION`
- `CALL_GRAPH`
- `OPERATIONAL_TEST`

The closure-wave review does not replace the required application-wide
integration, authorization, isolation, synchronization, recovery, and
operational evidence.

---

## PHASE 1 EVIDENCE SUMMARY

Completed characterization and closure-wave evidence covers:

- runtime composition and entry points;
- canonical PAPER call graph;
- risk authority;
- financial fill synchronization;
- account isolation;
- recovery lifecycle;
- API/dashboard ownership;
- compatibility and supersession;
- characterization test gaps;
- supplied current full backend regression evidence.

Evidence-supported outcome:

```text
PHASE1_VERIFIED_COUNT=2
PHASE1_PARTIAL_COUNT=10
PHASE1_OPEN_COUNT=0
PHASE1_NEEDS_VERIFICATION_COUNT=0
PHASE1_EVIDENCE_AUDIT_COMPLETE=YES
PHASE1_CLOSURE_WAVE_REVIEWED=YES
PHASE1_STATUS=CHARACTERIZED_NOT_COMPLETE
PHASE1_CLOSE_RECOMMENDATION=DO_NOT_CLOSE
```

The evidence does not support marking Phase 1 closed.

---

## PHASE 1 EXIT-GATE DISPOSITION

The closure wave did not satisfy the following required gates:

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

Phase 1 remains open. The controlled PAPER MVP remains not approved.

---

## NEXT ACTION

The next approved action is:

```text
route-to-lifecycle characterization
→ parallel execution-path fail-closed tests
→ PAPER isolation and duplicate-submission tests
→ cross-subsystem fill synchronization tests
→ ASGI/CLI equivalence tests
→ auxiliary-store and WebSocket account-isolation tests
→ complete route and authorization inventory
→ compatibility-path safety characterization
→ operational startup-to-PAPER smoke testing
```

No production code or tests are changed by this documentation update.
Autonomous LIVE trading remains disabled.

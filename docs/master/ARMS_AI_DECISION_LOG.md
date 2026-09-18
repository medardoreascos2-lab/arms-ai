# ARMS AI — DECISION LOG

> Permanent record of important ARMS AI decisions.

---

## PURPOSE

This file records:

- architectural decisions;
- direction changes;
- rejected or deferred functionality;
- safety decisions;
- product decisions;
- trading decisions;
- infrastructure decisions;
- reasons behind important changes.

Historical evidence and current technical decisions must remain distinguishable.

---

## DECISION FORMAT

Each new decision should use:

### DEC-XXXX — TITLE

**Date:** YYYY-MM-DD
**Status:** Proposed / Approved / Superseded / Rejected
**Area:** ...

**Context**

...

**Decision**

...

**Reason**

...

**Consequences**

...

**Supersedes**

...

**Superseded by**

...

---

## DECISIONS

### DEC-0001 — FORMAL CLOSURE OF PHASE 0 — CRITICAL STABILIZATION

**Date:** 2026-09-13
**Status:** Approved
**Area:** Safety / Reliability / Trading Execution / Risk Integrity

**Context**

Phase 0 contained eight critical stabilization requirements. Formal
recertification reported:

- `8/8 VERIFIED_CLOSED`;
- `PHASE0_PARTIAL_COUNT=0`;
- `PHASE0_OPEN_COUNT=0`;
- `PHASE0_NEEDS_VERIFICATION_COUNT=0`;
- `PHASE0_AUDIT_COMPLETE=YES`;
- `PHASE0_CLOSE_RECOMMENDATION=CLOSE`;
- documented backend regression: `5082 tests passed`.

**Decision**

Formally close Phase 0 — Critical Stabilization and retain its eight
requirements as `VERIFIED_CLOSED`.

**Reason**

The defined Phase 0 scope was certified with no partial, open, or
needs-verification requirements remaining.

**Consequences**

- Phase 0 is a certified baseline.
- Phase 0 closure does not certify the broader product or Phase 1.
- LIVE execution remains disabled.
- Historical consolidation remains separate from Phase 0 closure.

**Supersedes**

N/A

**Superseded by**

N/A

---

### DEC-0002 — REJECTED OR BLOCKED SIGNALS HAVE ZERO EXECUTION SIDE EFFECTS

**Date:** 2026-09-13
**Status:** Approved
**Area:** Safety / Risk / Trading Execution

**Context**

The governing safety policy and Phase 0 evidence require rejected, blocked,
stale, invalid, incomplete, unsafe, and unauthorized signals to be prevented
from producing execution effects.

**Decision**

Any rejected, blocked, stale, invalid, incomplete, unsafe, or unauthorized
signal must produce zero execution side effects.

This includes no:

- executable order preparation;
- broker or connector call;
- PAPER fill;
- position creation;
- portfolio or exposure mutation;
- account mutation implying execution;
- journal or history entry implying a fill;
- OCO or protective-order creation;
- fill-implying event.

`accepted: false` is an absolute execution boundary.

**Reason**

This is the central invariant in `AGENTS.md`, the Phase 0 certification, the
Requirements Matrix, and the execution architecture.

**Consequences**

Every execution entry point requires admission enforcement and regression
coverage of both returned results and side effects.

**Supersedes**

Any historical or implementation behavior that permits rejected signals to
reach preparation, execution, or state mutation.

**Superseded by**

N/A

---

### DEC-0003 — READ-ONLY OPERATIONS MUST NEVER TRADE

**Date:** 2026-09-13
**Status:** Approved
**Area:** Safety / API / Dashboard / Architecture

**Context**

Read operations must remain observational. Phase 0 formally certified the
dashboard read-side requirement within its defined scope.

**Decision**

GET endpoints, dashboard reads, analytics, reports, widgets, refreshes,
health checks, status requests, and WebSocket subscriptions must be
non-mutating and must not create execution side effects.

**Reason**

This requirement is established by `AGENTS.md` and the certified Phase 0
scope. Broader route-by-route verification remains subject to current tests.

**Consequences**

- Read services must not invoke order submission or execution mutation.
- Refresh and event-subscription paths remain separate from execution commands.
- Mutating actions require explicit and separately authorized operations.
- Read-side tests must inspect state and connector calls.

**Supersedes**

Any design in which dashboard loading, analytics, refresh, or subscriptions
implicitly trigger trading activity.

**Superseded by**

N/A

---

### DEC-0004 — PAPER AND LIVE EXECUTION REMAIN EXPLICITLY SEPARATED

**Date:** 2026-09-13
**Status:** Approved
**Area:** Safety / Execution / Architecture

**Context**

The repository contains PAPER execution components and broker abstractions.
Current evidence does not authorize or prove an operational LIVE path.

**Decision**

The approved execution boundary is controlled PAPER execution only.

PAPER execution must use an isolated PAPER connector or simulator and must not
reach a real-money broker path.

Autonomous LIVE trading and unvalidated real-money broker submission remain
blocked.

**Reason**

`AGENTS.md`, the Agent Policy, the reconciliation audits, and Phase 1
characterization prohibit automatic PAPER-to-LIVE conversion and require
separate authorization and validation for any future LIVE capability.

**Consequences**

- A broker abstraction does not authorize LIVE execution.
- PAPER mode must not dynamically select a LIVE connector.
- LIVE routes and defaults must remain unavailable or fail closed.
- Future LIVE work requires a separate approval and safety-validation phase.
- PAPER tests do not prove LIVE safety.

**Supersedes**

Historical plans or demonstrations that describe LIVE execution as a current
capability.

**Superseded by**

N/A

---

### DEC-0005 — PHYSICAL BROKER OCO AND PROTECTIVE ORDERS ARE NOT CURRENT CAPABILITIES

**Date:** 2026-09-13
**Status:** Approved
**Area:** Execution / Safety

**Context**

Current execution components support logical or internal protection state.
Current evidence does not establish validated physical broker submission.

**Decision**

Physical broker OCO, stop, target, and protective-order submission remains
unavailable.

Internal protection state must not be represented as broker-confirmed state.

**Reason**

Real-money execution is not approved, and repository evidence separates
logical protection from physical broker submission.

**Consequences**

Future physical submission requires separate broker authorization,
integration tests, safety review, and explicit product approval.

**Supersedes**

Historical execution visions that imply physical protections are currently
available.

**Superseded by**

N/A

---

### DEC-0006 — RISK CONTROLS FAIL CLOSED

**Date:** 2026-09-13
**Status:** Approved
**Area:** Risk / Safety / Trading

**Context**

Risk information may be missing, stale, inconsistent, invalid, or
unauthorized. Permissive fallback would create an unsafe execution path.

**Decision**

Missing, stale, inconsistent, invalid, or unauthorized risk information must
block execution.

This applies to daily loss, drawdown, contract limits, position sizing,
exposure, account restrictions, trading blocks, market freshness, economic
news, market state, stop-loss requirements, and authorization.

**Reason**

Fail-closed behavior is required by `AGENTS.md`, the Agent Policy, and the
reconciled architecture.

**Consequences**

- Risk checks must not silently substitute defaults.
- New risk changes require regression tests.
- Incomplete risk data cannot be treated as approval.
- Multiple risk authorities require explicit mapping before consolidation.

**Supersedes**

Any permissive fallback that allows execution when required risk information is
unavailable.

**Superseded by**

N/A

---

### DEC-0007 — EXPLICITLY SUPPLIED QUOTES ARE REQUIRED

**Date:** 2026-09-13
**Status:** Approved
**Area:** Market Data / Execution Safety / Data Integrity

**Context**

Synthetic bid/ask assumptions can create invalid execution prices and hide
missing market data.

**Decision**

Runtime quote authority may use only explicitly supplied bid/ask data.
Bid/ask quotes and spreads must not be inferred or manufactured from OHLC
candles, ATR, last price, assumed spreads, or other derived data.

**Reason**

The current quote-authority boundary and Requirements Matrix classify
synthetic spread generation as superseded.

**Consequences**

- Missing quote data remains missing.
- Admission and execution fail closed when required quotes are unavailable.
- Simulated data must be explicitly identified as simulated.
- Historical spread assumptions must not be restored.

**Supersedes**

Historical or convenience-based spread-generation assumptions.

**Superseded by**

N/A

---

### DEC-0008 — RUNTIME ACCOUNT CONFIGURATION IS AUTHORITATIVE

**Date:** 2026-09-13
**Status:** Approved
**Area:** Accounts / Risk / Data Integrity

**Context**

Historical account values were discussed as examples. Runtime behavior must
use current account configuration.

**Decision**

Current account configuration is authoritative for limits, restrictions, and
account behavior.

Historical Topstep example values remain historical evidence only:

- daily loss limit: `3000`;
- maximum drawdown: `4500`;
- profit target: `9000`.

**Reason**

Historical examples must not override account-specific runtime settings.

**Consequences**

- Historical limits must not be hardcoded as universal defaults.
- Risk behavior must derive from current configuration.
- Configuration changes require risk regression coverage.

**Supersedes**

Any historical account values treated as universal current defaults.

**Superseded by**

N/A

---

### DEC-0009 — RECOVERY MUST RECONSTRUCT AND VALIDATE STATE OR BLOCK EXECUTION

**Date:** 2026-09-13
**Status:** Approved
**Area:** Persistence / Recovery / Safety

**Context**

Loading a snapshot is not equivalent to reconstructing valid operational
state.

**Decision**

After startup or restart, the system must either reconstruct and semantically
validate required operational state or enter a blocked, non-executing state.

Recovery must not report success when state is incomplete, inconsistent,
corrupt, or unresolved.

**Reason**

This rule is established by `AGENTS.md`, the certified recovery scope, and the
recovery architecture.

**Consequences**

- Recovery success represents validated readiness.
- Pending PAPER operations require explicit reconciliation.
- Account, execution, portfolio, journal, and risk inconsistencies must block
  or fail recovery.
- Repeated recovery must not duplicate fills or mutations.

**Supersedes**

Any recovery behavior that reports success after restoring only a subset of
operational state.

**Superseded by**

N/A

---

### DEC-0010 — HISTORICAL EVIDENCE IS NOT CURRENT IMPLEMENTATION PROOF

**Date:** 2026-09-13
**Status:** Approved
**Area:** Governance / Architecture / Product

**Context**

Historical documents contain requirements, demonstrations, plans, and
completion claims that may not match the current repository.

**Decision**

Historical documents, prior API demonstrations, historical test reports,
filenames, class names, and roadmap statements establish historical intent or
reported prior behavior only.

Current status must be determined from current repository code, current tests,
current runtime composition, and current operational evidence.

**Reason**

The GREEN audit chain repeatedly established this evidence boundary.

**Consequences**

Historical demonstrations remain labeled historical, and requirements retain
explicit uncertainty and limitations.

**Supersedes**

Documentation practices that treat historical demonstrations as current
acceptance evidence.

**Superseded by**

N/A

---

### DEC-0011 — NO DESTRUCTIVE CONSOLIDATION WITHOUT RUNTIME CALL-GRAPH EVIDENCE

**Date:** 2026-09-13
**Status:** Approved
**Area:** Architecture / Maintainability / Safety

**Context**

The repository contains multiple versioned, legacy-looking, parallel, and
domain-specific components. Names alone do not establish ownership or
supersession.

**Decision**

No duplicate-looking, versioned, legacy, or parallel module may be deleted,
merged, or declared superseded solely from its filename or version number.

Before consolidation, establish active callers, execution paths, authority,
state mutation ownership, compatibility requirements, recovery ownership, and
route ownership.

**Reason**

The architecture audit identified unresolved duplication across execution,
risk, runtime, market data, intelligence, dashboard, and recovery paths.

**Consequences**

- Characterization tests precede consolidation.
- Compatibility-sensitive modules remain available until verified otherwise.
- Phase 1 excludes destructive consolidation.
- Safety behavior must be preserved.

**Supersedes**

Any proposal to remove modules merely because a newer-looking module exists.

**Superseded by**

N/A

---

### DEC-0012 — CANONICAL FINANCIAL STATE MUST BE ESTABLISHED BEFORE MVP APPROVAL

**Date:** 2026-09-13
**Status:** Proposed
**Area:** Accounts / Portfolio / Journal / Recovery

**Context**

The repository contains account, portfolio, journal, history, and recovery
components, but complete ownership and synchronization remain unresolved.

**Decision**

The controlled PAPER MVP should establish one authoritative source of
financial state and consistently link positions, account state, portfolio
state, PnL, risk state, journal, trade history, protections, dashboard events,
and persistence.

Fill application should be atomic or transactionally recoverable and
idempotent.

**Reason**

This remains an identified MVP requirement, not a proven implementation.

**Consequences**

MVP approval remains blocked until accepted-fill, rejected-fill,
duplicate-fill, and recovery tests cover the complete state path.

**Supersedes**

N/A

**Superseded by**

N/A

---

### DEC-0013 — CONTROLLED PAPER-ONLY MVP IS THE CURRENT PRODUCT TARGET

**Date:** 2026-09-13
**Status:** Proposed
**Area:** Product / Safety / Execution

**Context**

The repository has a substantial PAPER foundation, but complete runtime
composition, synchronization, and operational readiness are not yet proven.

**Decision**

The near-term target is a controlled PAPER-only trading assistant with
explicit simulated execution, fail-closed risk controls, no autonomous LIVE
capability, no physical real-money broker submission, transparent simulated
fills and slippage, dashboard support, and recovery support.

**Reason**

The GREEN MVP analysis identified this as the safe bounded target.

**Consequences**

Historical mobile, communication, commercialization, general-assistant, and
home-automation ideas remain outside this target. MVP approval requires the
documented end-to-end gates.

**Supersedes**

N/A

**Superseded by**

N/A

---

### DEC-0014 — PHASE 1 IS CORE RELIABILITY

**Date:** 2026-09-13
**Status:** Approved
**Area:** Planning / Architecture / Reliability

**Context**

Phase 0 is closed, and the GREEN audit chain completed the reconciliation
needed to define the next controlled scope.

**Decision**

Phase 1 is formally defined as `CORE RELIABILITY`.

Its objective is to establish a repository-derived authoritative runtime
architecture for the controlled PAPER trading system.

**Reason**

Architecture ownership and runtime composition must be characterized before
implementation expansion or consolidation.

**Consequences**

- Phase 1 is authorized for verification and characterization.
- Phase 1 does not certify implementation of its requirements.
- Phase 1 does not approve the broader PAPER MVP.
- Phase 1 excludes LIVE execution, product expansion, and destructive
  consolidation.

**Supersedes**

The prior roadmap state that Phase 1 remained undefined pending historical
consolidation.

**Superseded by**

N/A

---

### DEC-0015 — FUTURE LIVE CAPABILITY REQUIRES SEPARATE AUTHORIZATION AND VALIDATION

**Date:** 2026-09-13
**Status:** Approved
**Area:** Autonomy / Safety / Trading Execution

**Context**

Historical plans contemplated eventual LIVE execution. Current policy blocks
autonomous or unvalidated real-money execution.

**Decision**

Any future LIVE initiative requires separate approval covering explicit
configuration, explicit human authorization, independent safety validation,
broker-path isolation, risk and account verification, recovery and audit
validation, and proof that no unauthorized or autonomous path exists.

Until then, LIVE execution remains blocked.

**Reason**

This requirement is established by `AGENTS.md`, the Agent Policy, the
reconciliation audits, and Phase 1 evidence.

**Consequences**

- No current feature may silently enable LIVE trading.
- PAPER tests cannot prove LIVE safety.
- Broker abstractions remain non-authorizing.
- Autonomous execution cannot be introduced incrementally.

**Supersedes**

Historical plans describing eventual LIVE execution without the current
authorization boundary.

**Superseded by**

N/A

---

### DEC-0016 — GREEN AUDIT CHAIN 210-290 COMPLETES HISTORICAL RECONCILIATION

**Date:** 2026-09-13
**Status:** Approved
**Area:** Governance / Documentation / Architecture

**Context**

GREEN audits 210 through 290 reconciled historical requirements, current
capability evidence, architecture duplication, MVP gaps, the Requirements
Matrix, Master Memory, Decision Log, roadmap design, and Phase 1 scope.

**Decision**

Record the historical consolidation and audit chain 210 through 290 as
complete.

The resulting documentation must preserve historical ideas, distinguish
historical evidence from current proof, preserve Phase 0 certification, retain
unresolved classifications, preserve blocked and deferred scope, define Phase
1 Core Reliability, and avoid marking Phase 1 requirements implemented merely
because its scope is certified.

**Reason**

The audit chain reached its documentation outcome without changing production
code or tests.

**Consequences**

- The master documentation is the baseline for Phase 1 verification.
- No LIVE capability is enabled.
- No destructive consolidation is authorized.

**Supersedes**

The prior documentation state that historical consolidation remained pending.

**Superseded by**

N/A

---

### DEC-0017 — PHASE 1 IS CHARACTERIZED BUT NOT CLOSED

**Date:** 2026-09-13
**Status:** Approved
**Area:** Planning / Architecture / Reliability / Safety

**Context**

The completed Phase 1 evidence package characterized runtime composition,
canonical PAPER execution, risk authority, financial fill synchronization,
account isolation, recovery lifecycle, API/dashboard ownership, compatibility,
and characterization coverage.

The closure-wave review reports:

```text
PHASE1_VERIFIED_COUNT=2
PHASE1_PARTIAL_COUNT=10
PHASE1_OPEN_COUNT=0
PHASE1_NEEDS_VERIFICATION_COUNT=0
PHASE1_EVIDENCE_AUDIT_COMPLETE=YES
BACKEND_TEST_COUNT=630
BACKEND_TESTS_PASSED=5041
BACKEND_TEST_EXIT=0
```

The verified requirements are the compatibility/supersession register and the
canonical documentation baseline. The other ten requirements have meaningful
characterization evidence but unresolved application-wide boundaries.

**Decision**

Record Phase 1 Core Reliability as:

`CHARACTERIZED — CLOSURE WAVE REVIEWED — NOT CERTIFIED COMPLETE`

Do not mark Phase 1 closed and do not approve the broader PAPER MVP.

Retain the following as open reliability gaps:

- one process-wide canonical runtime owner;
- exclusive canonical PAPER-path use;
- one authority and precedence model for every risk limit;
- complete cross-subsystem financial synchronization;
- global duplicate-fill and interrupted-fill safety;
- complete account isolation across all callers and projections;
- complete route and authorization inventory;
- WebSocket authorization and account isolation;
- ASGI/CLI equivalence;
- compatibility-path safety characterization;
- operational startup-to-PAPER smoke testing.

**Reason**

The Phase 1 exit gates require application-wide evidence, not only component
tests, characterization documents, or a green full regression. The closure-wave
evidence does not support closure of every exit gate.

**Consequences**

- Phase 1 remains the active scope.
- Further work must remain limited to Core Reliability.
- No production-code expansion outside approved scope is authorized.
- No destructive consolidation is authorized.
- The PAPER MVP remains not approved.
- Autonomous LIVE trading and physical real-money execution remain blocked.
- The next work must target the documented characterization and integration
  gaps.

**Supersedes**

Any documentation implication that Phase 1 characterization, entry
certification, or a green full regression constitutes Phase 1 completion.

**Superseded by**

N/A

---

## PERMANENT SAFETY PRINCIPLES

The following principles remain binding:

1. Rejected or blocked signals have zero execution side effects.
2. Read-only operations never trade.
3. Risk controls fail closed.
4. PAPER and LIVE execution remain explicitly separated.
5. Recovery reconstructs and validates state or blocks execution.
6. Explicitly supplied quotes are required.
7. Synthetic spread generation is prohibited.
8. Runtime account configuration is authoritative.
9. Historical evidence is not current implementation proof.
10. Destructive consolidation requires call-graph and compatibility evidence.
11. Autonomous LIVE trading remains blocked.
12. Physical broker OCO and protective-order submission remain unavailable.

---

## DECISION LOG STATUS

Historical reconciliation status:

`COMPLETE — GREEN AUDIT CHAIN 210-290`

Phase 0 status:

`VERIFIED_CLOSED — FORMALLY CERTIFIED`

Phase 1 status:

`CHARACTERIZED — CLOSURE WAVE REVIEWED — NOT CERTIFIED COMPLETE`

Current next action:

`PHASE 1 CORE RELIABILITY GAP CLOSURE THROUGH CURRENT REPOSITORY CHARACTERIZATION AND INTEGRATION TESTS`


### DEC-0018 — V8 CONSOLIDATED ACCEPTANCE KEEPS PHASE 1 OPEN

**Date:** 2026-09-18
**Status:** Approved reporting under V8 scope; implementation redesign not authorized
**Area:** Phase 1 acceptance and trading safety

**Context**

The synchronized baseline is `d40745fa0bc1a481ef2d171753e392890b9109e0`.
The authoritative matrix contains 12 Phase 1 requirements. Prior scoped V3–V7
certifications pass baseline regression, but new real HTTP/direct PAPER tests
show prepared orders, broker calls and fills without a quote or certified
calendar/news permission. Core financial/account ownership alone cannot prevent
that admission bypass.

**Decision**

Record a negative [V8 acceptance certificate](../architecture/phase1_consolidated_acceptance_v8.md):
8 scoped CLOSED_CERTIFIED, 3 PARTIAL_REAL_GAP, 1 BLOCKED, 0 unclassified.
Leave PH1-REQ-002/003/004/011 and Phase 1 open. Preserve the failing rejection
tests without masking them. Stop production changes at V8 section H's boundary
for large cross-module integration. Do not stage, commit or push a red package.

**Reason**

A route-only guard leaves direct runtime submission exposed. Attaching the
existing optional order validator does not provide trusted quote/news evidence.
One mandatory operational admission contract must span composition, lifecycle,
API/analysis callers and the explicit isolated-replay boundary.

**Consequences**

Next package is `PHASE1_RUNTIME_MARKET_RISK_ADMISSION_INTEGRATION`. The current
audit does not enable LIVE, change credentials, or authorize Phase 2/PAPER MVP
release. Account isolation and financial/recovery certifications remain scoped
to their demonstrated invariants; they do not supersede the admission failure.

**Supersedes**

DEC-0017's historical ten-partial/two-verified count as the current inventory;
retains its decision that Phase 1 is not closed. Does not supersede prior valid
package-specific evidence or grant implementation-design approval.

**Superseded by**

DEC-0019 under the explicitly authorized V8.1 integration package.

---

## DEC-0019 — Close Phase 1 after mandatory runtime admission certification

**Status:** Accepted within authorized V8.1 PAPER scope.

**Context:** V8 exposed two HTTP/direct submissions that filled without market
permission. V8.1 explicitly authorized repairing the shared boundary and
recertifying the consolidated acceptance gate while preserving V8 evidence.

**Decision:** `TradeLifecycleServiceV2.submit_signal` owns mandatory operational
admission, delegating to existing market, risk and account authorities. Shared
composition eliminates missing guards; account-bound lower-level execution and
the compatibility journal facade cannot bypass admission. No duplicate risk or
freshness system is introduced. The original V8 tests are unchanged and green.

**Evidence:** [V8.1 certificate](../architecture/phase1_runtime_market_risk_admission_v81.md)
and its machine inventory record all 12 CLOSED_CERTIFIED requirements, zero
remaining Phase 1 gaps and zero full backend failures. Focused and consolidated
regressions protect rejection without preparation/fills/financial mutation,
positive PAPER execution, ownership, synchronization, isolation and recovery.

**Consequences:** PHASE1_STATUS=CLOSED for the documented PAPER scope; next
planned phase is PHASE2, Data and Market Intelligence. No LIVE, real broker,
credential change, product release or destructive consolidation is authorized.

**Supersedes:** DEC-0018's current non-closure disposition and V8 scope stop,
under the explicit V8.1 integration authorization. Retains all historical RED
observations and prior valid scoped certifications.


---

### DEC-0020 — Record Phase 2 MVP integration gaps without reopening Phase 1

**Date:** 2026-09-18
**Status:** Approved audit reporting under V9; follow-up implementation proposed
**Area:** PAPER MVP scope, integration and acceptance

**Context**

The synchronized V8.1 baseline `25280bdfbc01156cc027b5dd1955eb20107317a5`
certifies Phase 1. Actual application probes expose disconnected candle/analysis
routes and browser mutation/WebSocket authorization. Existing component tests
and intentionally simulated PAPER fills do not prove operational market input,
generated account-bound candidates or the complete browser/restart workflow.

**Decision**

Adopt the [V9 inventory and execution plan](../architecture/phase2_mvp_remaining_gap_audit_v9.md):
30 audited groups, 24 mandatory, 14 certified within their named boundaries;
58% capability completion; four P0, five P1 and one P2 gaps. Keep all existing
risk, current certified hours/news and account restrictions. Defer research
platform expansion, regional overlays, scheduled report delivery, mobile and
LIVE capabilities beyond this MVP. Configured intelligence checks still apply.

**Reason**

These are cross-module product integration gaps, not small local audit fixes.
Three packages connect canonical market-to-candidate, authorized browser
projection, then reproducible operational acceptance. No paid provider has been
selected; existing HTTP inputs and local replay avoid inventing an external
credential requirement. Source provenance remains mandatory.

**Consequences**

PHASE1_STATUS=CLOSED; MVP_READY=false. V9 changes tests and documentation only.
Full backend: 5,514 passed, zero failed, one unchanged skip. Frontend lint/build
and six tests pass; four pre-existing lint warnings remain. No complete browser
PAPER smoke or empirical strategy certification is claimed. Implement the first
named package next under its own defined scope; do not weaken authorization or
admission to connect the pipeline.

**Supersedes**

Older generic next-action wording only. DEC-0019 Phase 1 closure and its safety
contracts remain valid. No product release, LIVE or external broker approval.

**Superseded by**

None.


---

### DEC-0021 — Connect canonical application market input to candidate evaluation

**Date:** 2026-09-18
**Status:** Approved within explicit V10 scope
**Area:** PAPER market/intelligence integration and execution safety

**Context**

V9 exposed the coordinated PositionManagerV2/legacy PositionManager mismatch.
Two new public-ingress regression tests reproduced the 503 before production
changes. Simply broadening the type check would leave incompatible position
calls and implicit execution in the old composition. Real pipeline evidence
also exposed the missing calculated EMA-to-confluence alignment connection.

**Decision**

Use CanonicalMarketPipelineV2 as an orchestration boundary over the published
LiveCandleStore and existing LiveMarketAnalysisService/SignalGeneratorV2.
Serialize closed-candle ingestion; reject conflicts and late/future/invalid
observations. Bind real EMA alignment to existing confluence policy. Resolve
canonical position/account context and market/news authorities. Generate an
account/profile/generation-bound candidate and compatible admission request;
execute only through the separate existing canonical submission command.

**Reason**

Candidate approval is not risk permission or a fill. Controlled public inputs
must exercise existing owners without injecting private indicator state,
constructing fills or manipulating strategy thresholds. OHLC history must not
manufacture a quote or drive operational position-price monitoring. The existing
legacy disconnected-position safety boundary remains for compatibility callers.

**Consequences**

[The V10 certificate](../architecture/phase2_market_to_candidate_v10.md) and current
inventory close four mandatory groups: 18/24 (75%), P0=0, P1=5, P2=1. The complete
browser MVP remains open. No paid feed, LIVE execution, risk weakening or
empirical strategy certification is claimed. Next package:
PHASE2_AUTHORIZED_PAPER_DASHBOARD. Sustained source provisioning and complete
operational acceptance follow it.

**Supersedes**

DEC-0020's current market-to-candidate gap disposition and counts only. Retains
its browser/operational/provenance gaps and DEC-0019 Phase 1 safety closure.

**Superseded by**

None.


## DEC-0022 — Authorized local PAPER dashboard (V11)

**Decision**

Reuse AdminAuthorizationV2 for the operator-entered PAPER admin credential.
Protected HTTP uses the canonical header; browser WebSocket offers an encoded
credential protocol and negotiates only the public arms-dashboard-v1 protocol.
Store no browser token persistently and expose no server secret through public
build configuration. Use one frontend request wrapper and one connection
controller with account-generation and asynchronous-response guards.

**Reason**

Native browsers cannot set the existing WebSocket header. A transport adapter
preserves the single authority and pre-acceptance rejection. Account retirement
must invalidate every card, not only account/risk labels. Demo approvals are not
operational state; only canonical financial/risk and V10 candidate projections
belong in the authorized PAPER view.

**Consequences**

[The V11 certificate](../architecture/phase2_authorized_paper_dashboard_v11.md)
closes MVP-018/019/021: 21/24 (87%), P0=0, P1=2, P2=1. Candidate observation does
not submit trades. Legacy demonstration APIs/components remain available, but
are excluded from this view. Native header clients remain supported. Repeated
socket disconnect cleanup is cancellation-safe. Next is
PHASE2_PAPER_MVP_OPERATIONAL_ACCEPTANCE; sustained inputs, joined restart proof
and remaining validation provenance are still required. LIVE_EXECUTION=NO.

**Supersedes**

DEC-0021's browser-gap disposition and current counts only. Phase 1 closure,
V10 market-to-candidate evidence and operational/provenance limitations remain.

**Superseded by**

None.

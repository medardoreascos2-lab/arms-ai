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

Phase 0 — Critical Stabilization contained eight critical stabilization
requirements. Formal recertification was required before historical
consolidation and Phase 1 definition.

The recertification reported:

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

The eight requirements are:

1. Prevent blocked signals from executing.
2. Remove execution side effects from dashboard read operations.
3. Correct daily PnL synchronization.
4. Correct daily loss and trading-block synchronization.
5. Correct account-switching consistency.
6. Complete execution state recovery within the certified scope.
7. Resolve startup/runtime path inconsistencies within the certified scope.
8. Review and enforce API security boundaries within the certified scope.

Closure evidence:

- commit:
  `c13cd54d7ec0453c86e934ce117ce11764de5a4e`;
- message:
  `test: close Phase 0 critical stabilization gaps`.

**Reason**

The defined Phase 0 scope was certified with no partial, open, or
needs-verification requirements remaining.

**Consequences**

- Phase 0 is a certified baseline.
- The Requirements Matrix preserves individual traceability.
- Phase 0 closure does not certify the broader product.
- Phase 0 closure does not approve Phase 1 implementation.
- Historical consolidation remains a separate evidence activity.
- LIVE execution remains disabled.

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

`AGENTS.md`, the Agent Policy, the reconciliation audits, and the Phase 1
scope certification prohibit automatic PAPER-to-LIVE conversion and require
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

Real-money execution is not approved, and the repository evidence separates
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

This applies to:

- daily loss;
- maximum drawdown;
- contract limits;
- position sizing;
- exposure;
- account restrictions;
- trading-block state;
- market freshness;
- economic-news restrictions;
- market-state requirements;
- stop-loss requirements;
- authorization state.

**Reason**

Fail-closed risk behavior is required by `AGENTS.md`, the Agent Policy, and
the reconciled architecture.

**Consequences**

- Risk checks must not silently substitute defaults.
- New risk changes require regression tests.
- Incomplete risk data cannot be treated as approval.
- Multiple risk authorities require explicit mapping before consolidation.

**Supersedes**

Any permissive fallback that allows execution when required risk information
is unavailable.

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
Bid/ask quotes and spreads must not be inferred or manufactured from:

- OHLC candles;
- ATR;
- last price;
- assumed spread values;
- other derived data.

**Reason**

The current quote-authority boundary and Requirements Matrix classify synthetic
spread generation as superseded.

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

After startup or restart, the system must either:

1. reconstruct and semantically validate required operational state; or
2. enter a blocked, non-executing state.

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

Current status must be determined from:

- current repository code;
- current tests;
- current runtime composition;
- current operational evidence.

**Reason**

The GREEN audit chain repeatedly established this evidence boundary.

**Consequences**

- Historical demonstrations remain labeled historical.
- A file or claim alone cannot establish implementation.
- Requirements retain explicit uncertainty and limitations.
- Current evidence must support implementation classifications.

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

Before consolidation, establish:

- active imports and callers;
- signal-to-execution call paths;
- admission and preparation ownership;
- risk authority;
- state mutation ownership;
- compatibility requirements;
- recovery ownership;
- route ownership.

**Reason**

The architecture audit identified unresolved duplication across execution,
risk, runtime, market data, intelligence, dashboard, and recovery paths.

**Consequences**

- Characterization tests precede consolidation.
- Compatibility-sensitive modules remain available until verified otherwise.
- Safety behavior must be preserved.
- Phase 1 explicitly excludes destructive consolidation.

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
financial state and consistently link:

- positions;
- account state;
- portfolio state;
- realized and unrealized PnL;
- risk state;
- journal;
- trade history;
- protections;
- dashboard events;
- persistence.

Fill application should be atomic or transactionally recoverable and
idempotent.

**Reason**

This is an identified MVP requirement, but current evidence does not yet
prove complete implementation.

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

The near-term target is a controlled PAPER-only trading assistant with:

- explicit simulated execution;
- fail-closed risk controls;
- no autonomous LIVE capability;
- no physical real-money broker submission;
- transparent simulated fills and slippage;
- dashboard and recovery support.

**Reason**

The GREEN MVP analysis identified this as the safe bounded target.

**Consequences**

Historical mobile, communication, commercialization, general-assistant, and
home-automation ideas remain outside this target.

MVP approval requires the documented end-to-end gates.

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

Phase 0 is closed, and GREEN audits 210 through 290 completed the historical
and architectural reconciliation required to define the next controlled
scope.

**Decision**

Phase 1 is formally defined as `CORE RELIABILITY`.

Its objective is:

> Establish a repository-derived authoritative runtime architecture for the
> controlled PAPER trading system.

Phase 1 covers:

- runtime call-graph characterization;
- canonical PAPER path documentation;
- execution ownership;
- risk authority;
- account and financial-state ownership;
- fill synchronization;
- account-switch containment;
- lifecycle ownership;
- API/dashboard ownership;
- compatibility classification;
- characterization coverage;
- canonical documentation.

**Reason**

The audit chain established that architecture ownership and runtime
composition must be characterized before implementation expansion or
consolidation.

**Consequences**

- Phase 1 is authorized for entry-gate verification and characterization.
- Phase 1 does not certify implementation of its requirements.
- Phase 1 does not approve the broader PAPER MVP.
- Phase 1 excludes LIVE execution, product expansion, and destructive
  consolidation.
- Phase 1 exit requires current repository-derived evidence.

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

Any future LIVE initiative requires separate approval covering:

- explicit configuration;
- explicit human authorization;
- independent safety validation;
- broker-path isolation;
- risk and account verification;
- recovery and audit validation;
- proof that no unauthorized or autonomous path exists.

Until then, LIVE execution remains blocked.

**Reason**

This requirement is consistently established by `AGENTS.md`, the Agent Policy,
the reconciliation audits, and the Phase 1 certification.

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

The resulting documentation must:

- preserve historical ideas;
- distinguish historical evidence from current proof;
- preserve Phase 0 certification;
- retain unresolved classifications;
- preserve blocked and deferred scope;
- define Phase 1 Core Reliability;
- avoid marking Phase 1 requirements implemented merely because their scope is
  certified.

**Reason**

The audit chain reached its certified documentation outcome without changing
production code or tests.

**Consequences**

- The master documentation is now the baseline for Phase 1 entry verification.
- Phase 1 work must use repository-derived characterization.
- The roadmap's next action is Phase 1 entry-gate verification followed by
  runtime characterization.
- No LIVE capability is enabled.
- No destructive consolidation is authorized.

**Supersedes**

The prior documentation state that historical consolidation remained pending.

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

`APPROVED SCOPE — CORE RELIABILITY`

Current next action:

`PHASE 1 ENTRY-GATE VERIFICATION FOLLOWED BY REPOSITORY/RUNTIME CHARACTERIZATION`

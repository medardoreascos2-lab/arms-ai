# ARMS AI — MASTER MEMORY

> Single Source of Truth for ARMS AI.
> This document preserves historical intent while distinguishing it from
> current repository-backed implementation, characterization, and approval
> status.

---

## 1. PURPOSE

This document consolidates:

- historical product vision;
- current repository evidence;
- runtime characterization;
- Phase 0 certification;
- Phase 1 closure-wave evidence and limitations;
- architecture and ownership boundaries;
- requirements and decisions;
- deferred, blocked, superseded, duplicate, and conflicting concepts;
- current roadmap scope;
- unresolved technical questions.

Historical ideas are preserved. They are not automatically current requirements
or implementation claims.

Current repository code, current tests, runtime composition, and operational
evidence are authoritative for current technical status.

---

## 2. EVIDENCE POLICY

Evidence is interpreted in this order:

1. Current repository implementation and current tests.
2. Current runtime composition and operational evidence.
3. Current characterization and integration evidence.
4. Phase 1 closure-wave evidence.
5. Formal Phase 0 certification.
6. Completed GREEN audit evidence.
7. Historical documents and demonstrations.

The following do not prove current implementation by themselves:

- a filename;
- a class name;
- a roadmap statement;
- a historical API demonstration;
- a historical test count;
- a prior completion claim;
- an interface without runtime and test evidence.

Characterization and closure-wave evidence may establish partial behavior and
ownership without establishing application-wide equivalence, approval, or phase
closure.

---

## 3. CLASSIFICATION STATES

Current classifications are:

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

`VERIFIED_CLOSED` is reserved for formally certified closure. The currently
certified closed scope is Phase 0.

---

## 4. HISTORICAL PRODUCT VISION

ARMS AI historically evolved from a trading assistant into a broader assistant
platform.

Historical scope included:

- market and technical analysis;
- market structure and Smart Money concepts;
- confluence, probability, confidence, and multi-timeframe analysis;
- sessions and economic-news filters;
- risk management and position sizing;
- funded-account rules;
- PAPER execution and eventual LIVE execution;
- portfolio, journal, daily PnL, and drawdown;
- backtesting, optimization, walk-forward, Monte Carlo, and certification;
- machine learning, adaptive learning, and trading memory;
- dashboard, admin dashboard, APIs, WebSockets, monitoring, and reporting;
- mobile, Telegram, WhatsApp, voice, memberships, commercialization;
- general AI assistance and Home Assistant/Jarvis extensions.

Classification:

- controlled PAPER trading assistant foundation:
  `PARTIALLY_IMPLEMENTED`;
- complete historical ARMS AI vision:
  `HISTORICAL_IDEA` / `DEFERRED`;
- general assistant and Jarvis platform:
  `HISTORICAL_IDEA`.

The historical vision is not the current MVP definition.

---

## 5. HISTORICAL TRADING INTENT

Historical trading intent included:

- Nasdaq futures, especially NQ and MNQ;
- higher-timeframe context and trend;
- 15-minute panorama;
- 5-minute setups;
- 1-minute execution refinement;
- EMA, RSI, ATR, BOS, CHOCH, FVG, liquidity, session highs/lows;
- confluence, probability, confidence, A+ grading, and risk/reward;
- few high-quality trades rather than overtrading.

The exact historical timeframe workflow remains:

`HISTORICAL_IDEA`

Current repository components support selected market structure, trend, context,
regime, Smart Money, liquidity, confluence, probability, confidence, and
multi-timeframe behavior. Their existence does not prove one canonical active
runtime pipeline.

---

## 6. CURRENT TECHNICAL EVIDENCE

Current repository evidence supports selected components for:

- trade plans and trading decisions;
- market-state storage;
- market structure, trend, context, and regime;
- Smart Money and liquidity;
- confluence, probability, confidence, and multi-timeframe analysis;
- market-data hub, price-feed processing, and quote authority;
- market-hours and certified-calendar infrastructure;
- account and funding-firm profiles;
- position sizing and risk managers;
- signal controls and execution preparation;
- PAPER execution, simulated fills, and slippage;
- position lifecycle and logical protection/OCO state;
- portfolio, reporting, and analytics;
- backtesting, walk-forward, Monte Carlo, and certification;
- signal and trade history;
- selected API, dashboard, and WebSocket components;
- AI response contracts, trade outcome analysis, trading memory, and learning.

These are component or selected-path evidence statements. They do not
automatically prove:

- one canonical runtime path;
- complete application-wide composition;
- complete route authorization;
- complete account isolation;
- complete cross-subsystem synchronization;
- production readiness;
- LIVE execution;
- physical broker order submission.

---

## 7. PHASE 0 CERTIFIED STATE

Phase 0 — Critical Stabilization is formally closed.

Certified values:

- `PHASE0_REQUIREMENTS=8`;
- `PHASE0_VERIFIED_CLOSED=8`;
- `PHASE0_PARTIAL_COUNT=0`;
- `PHASE0_OPEN_COUNT=0`;
- `PHASE0_NEEDS_VERIFICATION_COUNT=0`;
- `PHASE0_AUDIT_COMPLETE=YES`;
- `PHASE0_CLOSE_RECOMMENDATION=CLOSE`.

The eight certified requirements are:

1. Prevent blocked signals from executing.
2. Remove execution side effects from dashboard read operations.
3. Correct daily PnL synchronization.
4. Correct daily loss and trading-block synchronization.
5. Correct account-switching consistency.
6. Complete execution-state recovery within the certified scope.
7. Resolve startup/runtime path inconsistencies within the certified scope.
8. Review and enforce API security boundaries within the certified scope.

Evidence:

- documented Phase 0 regression: `5082 tests passed`;
- closure commit:
  `c13cd54d7ec0453c86e934ce117ce11764de5a4e`;
- closure message:
  `test: close Phase 0 critical stabilization gaps`.

This certification is limited to the eight Phase 0 requirements.

---

## 8. PHASE 1 — CORE RELIABILITY

Current status:

`CHARACTERIZED — CLOSURE WAVE REVIEWED — NOT CERTIFIED COMPLETE`

Objective:

> Establish a repository-derived authoritative runtime architecture for the
> controlled PAPER trading system.

The Phase 1 closure wave reviewed the accumulated repository-derived
characterization, focused regression evidence, and supplied full backend
regression evidence.

Closure-wave evidence records:

```text
PHASE1_VERIFIED_COUNT=2
PHASE1_PARTIAL_COUNT=10
PHASE1_OPEN_COUNT=0
PHASE1_NEEDS_VERIFICATION_COUNT=0
BACKEND_TEST_COUNT=630
BACKEND_TESTS_PASSED=5041
BACKEND_TEST_EXIT=0
```

The full backend regression is green based on supplied repository evidence. It
was not executed by this documentation update.

The closure-wave review does not promote the ten partially verified
requirements to verified or closed status. Phase 1 remains open because the
evidence does not prove complete behavior across every application, CLI,
legacy, parallel, API, dashboard, persistence, or account-bound path.

### 8.1 Strongest observed PAPER path

```text
validated supplied market data
→ market context and intelligence
→ signal or decision
→ TradeLifecycleServiceV2 admission
→ account and risk checks
→ trade-plan and order validation
→ ExecutionRiskGateV1
→ PAPER connector and simulated fill
→ PositionManagerV2
→ logical protection and OCO state
→ PortfolioManagerV2
→ AccountStateManagerV2
→ journal and trade history
→ dashboard events
→ durable persistence
→ recovery and semantic validation
```

This is the strongest characterized candidate, not proof that every execution
entry point uses it exclusively.

### 8.2 Phase 1 requirement disposition

The following remain partially verified:

- `PH1-REQ-001` — runtime call graph;
- `PH1-REQ-002` — canonical PAPER path;
- `PH1-REQ-003` — execution ownership;
- `PH1-REQ-004` — risk authority;
- `PH1-REQ-005` — financial-state ownership;
- `PH1-REQ-006` — fill synchronization;
- `PH1-REQ-007` — account-switch containment;
- `PH1-REQ-008` — lifecycle ownership;
- `PH1-REQ-009` — API/dashboard inventory;
- `PH1-REQ-011` — characterization coverage.

The following are verified at the documentation/evidence level only:

- `PH1-REQ-010` — compatibility and supersession register;
- `PH1-REQ-012` — canonical documentation baseline.

No Phase 1 requirement is certified closed by the closure wave.

### 8.3 Closure-wave findings

The closure wave confirms substantial evidence for:

- ASGI, direct FastAPI, and CLI entry points;
- runtime context and account-bound service construction;
- startup, shutdown, persistence, recovery, and pending-operation layers;
- the strongest observed PAPER execution lifecycle;
- risk-authority ownership and unresolved precedence;
- financial-state, journal, history, event, and recovery boundaries;
- coordinated account switching;
- API/dashboard ownership and selected authorization;
- compatibility and supersession classifications;
- focused safety and characterization tests;
- supplied green full backend regression evidence.

The closure wave does not prove:

- one process-wide canonical runtime owner;
- exclusive use of one PAPER path;
- one risk authority and precedence model for every limit;
- atomic cross-subsystem financial synchronization;
- global duplicate-fill or retry idempotency;
- complete interrupted-fill recovery;
- complete account isolation across every caller and projection;
- complete route and authorization inventory;
- WebSocket authorization and account isolation;
- ASGI/CLI equivalence;
- complete compatibility-path safety;
- operational startup-to-PAPER smoke testing.

Phase 1 is therefore not closed, and the broader PAPER MVP is not approved.

---

## 9. RISK MANAGEMENT

### 9.1 Historical requirements

Historical risk requirements included:

- account-specific profiles;
- daily-loss and drawdown enforcement;
- contract limits and position sizing;
- trade validation and news blocking;
- trading blocks and funded-account restrictions;
- explicit confirmation before real execution;
- no uncontrolled LIVE trading.

Historical Topstep 150K values are retained only as examples:

- daily loss limit: `3000`;
- maximum drawdown: `4500`;
- profit target: `9000`.

They must not override runtime account configuration.

### 9.2 Current status

Current evidence supports:

- account-specific profiles: `VERIFIED_IMPLEMENTED`;
- funding-firm profiles and contract limits: `VERIFIED_IMPLEMENTED`;
- position sizing: `VERIFIED_IMPLEMENTED` at component level;
- daily PnL synchronization: `VERIFIED_CLOSED` within Phase 0;
- daily loss and trading-block synchronization: `VERIFIED_CLOSED`;
- trade validation: `VERIFIED_IMPLEMENTED` at component level;
- risk-event persistence: `VERIFIED_IMPLEMENTED`;
- maximum drawdown enforcement: `PARTIALLY_IMPLEMENTED`;
- portfolio exposure enforcement: `PARTIALLY_IMPLEMENTED`;
- economic-news enforcement: `PARTIALLY_IMPLEMENTED`;
- complete fail-closed behavior across every path: `NEEDS_VERIFICATION`;
- one authoritative source for every risk limit: `NEEDS_VERIFICATION`.

### 9.3 Absolute safety invariant

Any rejected, blocked, stale, invalid, incomplete, unsafe, or unauthorized
signal must produce zero execution side effects.

This means no:

- executable order;
- broker or connector call;
- PAPER fill;
- position;
- protection or OCO state;
- portfolio mutation;
- account mutation implying execution;
- journal execution record;
- fill-implying event.

The invariant is strongly supported on characterized lifecycle paths but is not
proven across every parallel, legacy, CLI, and API path.

---

## 10. EXECUTION

Current approved execution scope is controlled PAPER execution only.

Current evidence supports:

- signal-to-prepared-order conversion;
- PAPER execution and simulated fills;
- transparent slippage behavior;
- position lifecycle;
- logical OCO and protective-order state;
- break-even, trailing-stop, and partial-take-profit components;
- selected accepted and rejected lifecycle behavior.

Remaining restrictions and gaps:

- complete canonical execution call path:
  `PARTIALLY_IMPLEMENTED`;
- complete PAPER/LIVE isolation:
  `NEEDS_VERIFICATION`;
- duplicate-submission idempotency:
  `NEEDS_VERIFICATION`;
- complete partial and failed-fill semantics:
  `NEEDS_VERIFICATION`;
- complete cross-subsystem synchronization:
  `NEEDS_VERIFICATION`;
- physical broker protections:
  `NOT_IMPLEMENTED`;
- autonomous LIVE trading:
  `BLOCKED`;
- physical real-money broker submission:
  `BLOCKED`.

The presence of broker abstractions does not authorize or prove LIVE execution.

---

## 11. FINANCIAL STATE, ACCOUNT ISOLATION, AND RECOVERY

The strongest observed financial-state direction is:

```text
PAPER fill
→ position state
→ PortfolioManagerV2
→ AccountStateManagerV2
→ journal/history and dashboard projections
→ durable execution state
```

The characterized path supports:

- portfolio-to-account synchronization;
- realized and unrealized PnL separation;
- daily PnL and trading-block behavior;
- tested partial-close and final-close double-counting protections;
- logical protection/OCO synchronization;
- coordinated account-switch containment;
- execution-state persistence and recovery.

The following remain unresolved:

- atomicity across all fill participants;
- global duplicate-fill prevention;
- complete journal durability and fill linkage;
- complete cross-subsystem recovery;
- event ordering, deduplication, and account isolation;
- auxiliary-store isolation;
- recovery after interrupted fills;
- equivalence across API, CLI, and legacy callers.

Recovery must reconstruct and validate required operational state or enter a
blocked, non-executing state. It must never report successful recovery for
incomplete, inconsistent, corrupt, ambiguous, or unauthorized state.

---

## 12. DASHBOARD AND FRONTEND

Current evidence supports selected:

- dashboard API and client components;
- risk and trade-lifecycle event publication;
- event bus and dispatcher;
- WebSocket hub and broadcaster;
- refresh and live-data services;
- widgets;
- frontend page and layout;
- dashboard API and read-side tests.

Current classifications:

- selected dashboard components:
  `VERIFIED_IMPLEMENTED`;
- certified dashboard read-side safety:
  `VERIFIED_CLOSED`;
- complete dashboard product:
  `PARTIALLY_IMPLEMENTED`;
- route-level authorization:
  `PARTIALLY_IMPLEMENTED`;
- complete WebSocket authorization and account isolation:
  `NEEDS_VERIFICATION`.

The following must remain non-mutating:

- GET requests;
- dashboard reads;
- analytics;
- reports;
- widgets;
- refresh;
- health and status checks;
- WebSocket subscriptions.

---

## 13. MARKET DATA AND PROVIDERS

Current evidence supports:

- market-data hub;
- price-feed processing;
- runtime quote authority;
- market-hours resolution;
- certified calendar and special-hours handling.

Remaining unresolved capabilities:

- external live market-data provider:
  `NEEDS_VERIFICATION`;
- TradingView:
  `NEEDS_VERIFICATION` / `DEFERRED`;
- external economic-news provider:
  `NEEDS_VERIFICATION`;
- complete provider failure and reconnection behavior:
  `NEEDS_VERIFICATION`;
- one freshness and quote authority consumed by every execution path:
  `NEEDS_VERIFICATION`.

Synthetic bid/ask or spread generation is:

`SUPERSEDED`

The runtime must use explicitly supplied bid/ask data and must not infer spreads
from candles, ATR, last price, or assumptions.

---

## 14. SECURITY AND OPERATIONS

Phase 0 certified the API security boundary within its defined scope.

Broader classifications remain:

- complete route-level authorization:
  `PARTIALLY_IMPLEMENTED`;
- complete account-level authorization isolation:
  `NEEDS_VERIFICATION`;
- complete WebSocket authorization:
  `NEEDS_VERIFICATION`;
- health and readiness:
  `NEEDS_VERIFICATION`;
- structured operational logging:
  `NEEDS_VERIFICATION`;
- monitoring:
  `NEEDS_VERIFICATION`;
- backup, restore, quarantine, and rollback:
  `NEEDS_VERIFICATION`;
- production deployment:
  `NEEDS_VERIFICATION`.

Secrets, credentials, tokens, and private keys must never be committed or
exposed.

---

## 15. CURRENT NEXT ACTION

Continue Phase 1 Core Reliability gap closure in this order:

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

No Phase 1 closure claim may be made until the applicable exit gates are
satisfied by current repository and test evidence.

---

## 16. HISTORICAL IDEAS, DEFERRED SCOPE, AND BLOCKED SCOPE

Historical ideas retained as `HISTORICAL_IDEA` or `DEFERRED` include:

- broader assistant platform;
- exact 15m/5m/1m historical workflow;
- historical API demonstrations;
- Telegram, WhatsApp, mobile, and voice;
- general Jarvis assistant;
- Home Assistant;
- facial recognition and robotics;
- memberships and commercial packages;
- commercial signal distribution;
- historical pricing;
- advanced autonomy.

Deferred technical capabilities include:

- TradingView;
- additional external market-data providers;
- external economic-news ingestion;
- machine learning;
- adaptive intelligence;
- persistent general-assistant memory;
- production deployment;
- production-grade monitoring;
- physical broker protections.

Blocked capabilities include:

- autonomous LIVE trading;
- unauthorized real-money broker execution;
- physical real-money order submission;
- automatic PAPER-to-LIVE conversion;
- any path bypassing risk, authorization, freshness, account, or recovery
  controls.

---

## 17. CURRENT MEMORY STATUS

Status:

`HISTORICAL CONSOLIDATION COMPLETE; PHASE 1 CLOSURE WAVE REVIEWED; NOT CLOSED`

The controlled PAPER product remains a bounded target whose complete end-to-end
runtime composition, synchronization, operational readiness, and MVP approval
require additional evidence.

The permanent safety principles remain:

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

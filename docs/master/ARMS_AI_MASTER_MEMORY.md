# ARMS AI — MASTER MEMORY

> Single Source of Truth for ARMS AI.
> This document preserves historical intent while distinguishing it from
> current repository-backed implementation status.

---

## 1. PURPOSE

This document consolidates:

- historical product vision;
- current repository evidence;
- Phase 0 certification;
- GREEN audit-chain conclusions;
- architecture and ownership boundaries;
- requirements and decisions;
- deferred, blocked, superseded, duplicate, and conflicting concepts;
- current roadmap scope;
- unresolved technical questions.

Historical ideas are preserved. They are not automatically current
requirements or implementation claims.

Current repository code and current tests are authoritative for technical status.

---

## 2. EVIDENCE POLICY

Evidence is interpreted in this order:

1. Current repository implementation and current tests.
2. Current runtime composition and operational evidence.
3. Formal Phase 0 certification.
4. Completed GREEN audit evidence.
5. Historical documents, prior discussions, and historical demonstrations.

The following do not prove current implementation by themselves:

- a filename;
- a class name;
- a roadmap statement;
- a historical API demonstration;
- a historical test count;
- a prior completion claim;
- the existence of an interface without runtime and test evidence.

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

`VERIFIED_CLOSED` is reserved for formally certified closure, currently the
defined Phase 0 scope.

---

## 4. HISTORICAL PRODUCT VISION

ARMS AI historically evolved from a trading assistant into a broader assistant
platform.

Historical scope included:

- market analysis;
- technical analysis;
- market structure;
- Smart Money concepts;
- confluence;
- probability and confidence;
- multi-timeframe analysis;
- sessions;
- economic-news filters;
- risk management;
- position sizing;
- funded-account rules;
- PAPER execution;
- eventual LIVE execution with explicit safety controls;
- portfolio management;
- journal;
- daily PnL and drawdown;
- backtesting;
- optimization;
- walk-forward validation;
- Monte Carlo analysis;
- strategy certification;
- machine learning;
- adaptive learning;
- trading memory;
- dashboard;
- admin dashboard;
- mobile application;
- Telegram;
- WhatsApp;
- voice assistant;
- APIs and WebSockets;
- monitoring;
- reporting;
- memberships;
- commercialization;
- general AI assistance;
- Home Assistant and Jarvis extensions.

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
- EMA, RSI, and ATR;
- BOS and CHOCH;
- fair value gaps;
- liquidity;
- session highs and lows;
- previous highs and lows;
- confluence;
- probability and confidence;
- A+ grading;
- risk/reward validation;
- few high-quality trades rather than overtrading.

The exact historical timeframe workflow remains:

`HISTORICAL_IDEA`

Current repository components support selected market structure, trend, context,
regime, Smart Money, liquidity, confluence, probability, confidence, and
multi-timeframe capabilities. The existence of these components does not prove
one canonical active runtime pipeline.

---

## 6. CURRENT TECHNICAL EVIDENCE

The repository provides evidence for selected components, including:

- trade-plan and trading-decision models;
- market-state storage;
- market structure;
- trend, context, and regime analysis;
- Smart Money and liquidity components;
- confluence;
- probability and confidence components;
- multi-timeframe decision components;
- market-data hub and price-feed processing;
- runtime quote authority;
- market-hours and certified-calendar infrastructure;
- account and funding-firm profiles;
- position sizing;
- risk managers and signal controls;
- execution preparation;
- PAPER execution components;
- simulated fill and slippage behavior;
- position lifecycle;
- logical OCO and protective-order state;
- portfolio management and analytics;
- backtesting, walk-forward, Monte Carlo, and certification infrastructure;
- signal and trade history persistence;
- selected API, dashboard, and WebSocket components;
- AI provider response contract;
- trade outcome analysis;
- trading-memory and learning components.

These are component-level evidence statements. They do not automatically prove:

- one canonical runtime path;
- complete end-to-end composition;
- complete route authorization;
- complete cross-subsystem synchronization;
- production readiness;
- LIVE execution;
- physical broker order submission.

---

## 7. RISK MANAGEMENT

### 7.1 Historical requirements

Historical risk requirements included:

- account-specific risk profiles;
- daily-loss enforcement;
- maximum drawdown enforcement;
- contract limits;
- position sizing;
- trade validation;
- news blocking;
- trading blocks;
- funded-account restrictions;
- explicit confirmation before real execution;
- no uncontrolled LIVE trading.

Historical Topstep 150K values are retained only as historical examples:

- daily loss limit: `3000`;
- maximum drawdown: `4500`;
- profit target: `9000`.

They must not override runtime account configuration.

### 7.2 Current status

Current evidence supports:

- account-specific profiles: `VERIFIED_IMPLEMENTED`;
- funding-firm profiles and contract limits: `VERIFIED_IMPLEMENTED`;
- position sizing: `VERIFIED_IMPLEMENTED`;
- daily PnL synchronization: `VERIFIED_CLOSED` within Phase 0;
- daily loss and trading-block synchronization: `VERIFIED_CLOSED`;
- trade validation: `VERIFIED_IMPLEMENTED`;
- risk-event persistence: `VERIFIED_IMPLEMENTED`;
- maximum drawdown enforcement: `PARTIALLY_IMPLEMENTED`;
- portfolio exposure enforcement: `PARTIALLY_IMPLEMENTED`;
- economic-news enforcement: `PARTIALLY_IMPLEMENTED`;
- complete fail-closed behavior across every path: `NEEDS_VERIFICATION`;
- one authoritative source for every risk limit: `NEEDS_VERIFICATION`.

### 7.3 Absolute safety invariant

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

---

## 8. EXECUTION

### 8.1 Current PAPER boundary

Current approved execution scope is controlled PAPER execution only.

Current evidence supports:

- signal-to-prepared-order conversion;
- PAPER execution components;
- simulated fills and slippage;
- position lifecycle;
- logical OCO;
- logical protective-order state;
- break-even, trailing-stop, and partial-take-profit components.

The following remain unresolved or restricted:

- complete canonical execution call path:
  `NEEDS_VERIFICATION`;
- complete PAPER/LIVE isolation proof:
  `NEEDS_VERIFICATION`;
- duplicate-submission idempotency:
  `NEEDS_VERIFICATION`;
- complete partial-fill and failed-fill semantics:
  `NEEDS_VERIFICATION`;
- complete cross-subsystem synchronization:
  `NEEDS_VERIFICATION`;
- physical broker OCO and protective-order submission:
  `NOT_IMPLEMENTED`;
- autonomous LIVE trading:
  `BLOCKED`;
- physical real-money broker submission:
  `BLOCKED`.

The presence of broker abstractions does not authorize or prove LIVE execution.

### 8.2 Historical execution intent

Historical intent included eventual LIVE broker execution and physical protective
orders. Those remain historical or blocked concepts under the current safety
policy.

---

## 9. BACKTESTING AND STRATEGY VALIDATION

Historical requirements included:

- historical backtesting;
- optimization;
- walk-forward testing;
- Monte Carlo simulation;
- strategy scoring and grading;
- strategy certification;
- strategy registration;
- machine learning from historical outcomes;
- adaptive learning.

Current component evidence supports:

- historical candle validation;
- deterministic replay;
- backtest execution;
- backtesting jobs;
- equity curves and exports;
- walk-forward splitting and reporting;
- walk-forward optimization;
- Monte Carlo simulation and reporting;
- validation scores and grades;
- strategy certification and registry.

Current limitations:

- complete dataset and strategy traceability:
  `PARTIALLY_IMPLEMENTED`;
- prevention of silent dataset or strategy substitution:
  `NEEDS_VERIFICATION`;
- machine learning from historical outcomes:
  `NEEDS_VERIFICATION`;
- adaptive learning:
  `NEEDS_VERIFICATION`.

Backtesting infrastructure does not itself prove production strategy validity.

---

## 10. AI, MEMORY, AND LEARNING

Historical concepts included:

- external AI providers;
- trading memory;
- learning from trade outcomes;
- machine learning;
- adaptive intelligence;
- persistent assistant memory;
- general AI assistance;
- trading explanations.

Current classifications:

- AI provider response contract:
  `VERIFIED_IMPLEMENTED`;
- trade outcome analysis:
  `VERIFIED_IMPLEMENTED`;
- trading-memory components:
  `PARTIALLY_IMPLEMENTED`;
- learning from trade outcomes:
  `PARTIALLY_IMPLEMENTED`;
- concrete external AI providers:
  `NEEDS_VERIFICATION`;
- machine learning:
  `NEEDS_VERIFICATION`;
- adaptive intelligence:
  `NEEDS_VERIFICATION`;
- persistent general-assistant memory:
  `NEEDS_VERIFICATION`;
- complete general assistant:
  `HISTORICAL_IDEA`.

AI and learning components are advisory unless separately validated. They may
not bypass deterministic risk, account, authorization, freshness, or execution
controls.

---

## 11. DASHBOARD AND FRONTEND

Historical goals included:

- user dashboard;
- admin dashboard;
- account and risk status;
- positions;
- PnL;
- signal explanation;
- trade history;
- reporting;
- monitoring;
- WebSockets;
- live updates;
- productization.

Current evidence supports selected:

- dashboard API and client components;
- risk and trade-lifecycle event publication;
- event bus and dispatcher;
- WebSocket hub and broadcaster;
- refresh and live-data services;
- widgets;
- frontend page and layout;
- dashboard API tests.

Current classifications:

- selected dashboard API and client components:
  `VERIFIED_IMPLEMENTED`;
- dashboard events and WebSocket components:
  `VERIFIED_IMPLEMENTED`;
- certified dashboard read-side safety:
  `VERIFIED_CLOSED`;
- complete dashboard product surface:
  `PARTIALLY_IMPLEMENTED`;
- admin dashboard:
  `NEEDS_VERIFICATION`;
- complete analytics and monitoring surface:
  `PARTIALLY_IMPLEMENTED`;
- route-level authorization:
  `PARTIALLY_IMPLEMENTED`;
- complete WebSocket authorization and account isolation:
  `NEEDS_VERIFICATION`.

The following operations must remain non-mutating:

- GET requests;
- dashboard reads;
- analytics;
- reports;
- widgets;
- refresh;
- health and status checks;
- WebSocket subscriptions.

---

## 12. ACCOUNTS, PORTFOLIO, JOURNAL, AND RECOVERY

Current evidence supports:

- durable account state:
  `VERIFIED_IMPLEMENTED`;
- account-switch containment:
  `VERIFIED_CLOSED` within certified scope;
- portfolio management and analytics:
  `VERIFIED_IMPLEMENTED`;
- trade history persistence:
  `VERIFIED_IMPLEMENTED`;
- signal history persistence:
  `VERIFIED_IMPLEMENTED`;
- journal implementation:
  `PARTIALLY_IMPLEMENTED`;
- execution-state capture and restore:
  `VERIFIED_IMPLEMENTED`;
- semantic validation:
  `VERIFIED_IMPLEMENTED`;
- certified execution recovery:
  `VERIFIED_CLOSED` within Phase 0;
- pending-operation reconciliation:
  `PARTIALLY_IMPLEMENTED`;
- complete account, portfolio, journal, risk, and dashboard recovery:
  `PARTIALLY_IMPLEMENTED`;
- idempotent cross-subsystem recovery:
  `NEEDS_VERIFICATION`;
- recovery after interrupted PAPER fill:
  `NEEDS_VERIFICATION`.

The authoritative owner of balance, equity, realized PnL, unrealized PnL,
exposure, drawdown, and journal linkage is not fully established across the
complete runtime path.

Required recovery rule:

> Recovery must reconstruct and validate required operational state or enter a
> blocked, non-executing state. It must never report success for incomplete or
> inconsistent state.

---

## 13. MARKET DATA AND PROVIDERS

Current evidence supports:

- market-data hub;
- price-feed processing;
- runtime quote authority;
- market-hours resolution;
- certified calendar and special-hours handling.

The following remain unresolved:

- external live market-data provider:
  `NEEDS_VERIFICATION`;
- TradingView:
  `NEEDS_VERIFICATION` / `DEFERRED`;
- external economic-news provider:
  `NEEDS_VERIFICATION`;
- complete provider failure and reconnection behavior:
  `NEEDS_VERIFICATION`.

Synthetic bid/ask or spread generation is:

`SUPERSEDED`

The runtime must use explicitly supplied bid/ask data and must not infer spreads
from candles, ATR, last price, or assumptions.

---

## 14. SECURITY AND OPERATIONS

Phase 0 certified the API security boundary within its defined scope.

Broader classifications:

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

## 15. PHASE 0 CERTIFIED STATE

Phase 0 is formally closed.

Certified values:

- `PHASE0_REQUIREMENTS=8`;
- `PHASE0_VERIFIED_CLOSED=8`;
- `PHASE0_PARTIAL_COUNT=0`;
- `PHASE0_OPEN_COUNT=0`;
- `PHASE0_NEEDS_VERIFICATION_COUNT=0`;
- `PHASE0_AUDIT_COMPLETE=YES`;
- `PHASE0_CLOSE_RECOMMENDATION=CLOSE`.

Evidence:

- documented backend regression: `5082 tests passed`;
- closure commit:
  `c13cd54d7ec0453c86e934ce117ce11764de5a4e`;
- closure message:
  `test: close Phase 0 critical stabilization gaps`.

This certification is limited to the eight Phase 0 requirements.

---

## 16. HISTORICAL CONSOLIDATION AND AUDIT CHAIN 210-290

Status:

`COMPLETE`

The GREEN audit chain 210 through 290 completed:

- capability mapping;
- historical-requirements reconciliation;
- architecture duplication audit;
- MVP gap analysis;
- Requirements Matrix reconciliation;
- Master Memory reconciliation;
- Decision Log reconciliation;
- final roadmap design;
- Phase 1 scope certification.

The audit chain established that:

- historical evidence is not current implementation proof;
- repository code and tests remain authoritative;
- Phase 0 remains formally closed;
- the broader historical vision is not the current MVP;
- unresolved capabilities retain explicit classifications;
- destructive consolidation is not authorized without call-graph evidence;
- autonomous LIVE trading remains blocked;
- the next approved scope is Phase 1 Core Reliability.

No production code or tests were changed by the audit chain.

---

## 17. PHASE 1 — CORE RELIABILITY

Status:

`DEFINED — CERTIFIED FOR ENTRY-GATE VERIFICATION`

Objective:

> Establish a repository-derived authoritative runtime architecture for the
> controlled PAPER trading system.

Phase 1 requirements:

1. Repository-derived runtime call graph.
2. Canonical PAPER execution path.
3. Execution ownership boundaries.
4. Risk-authority map.
5. Account and financial-state ownership.
6. Fill synchronization contract.
7. Account-switch containment.
8. Runtime lifecycle ownership.
9. API and dashboard ownership inventory.
10. Compatibility and supersession register.
11. Characterization coverage.
12. Canonical documentation baseline.

Phase 1 is not implementation certification. Each requirement remains open until
repository-derived evidence and characterization tests support its status.

### 17.1 Phase 1 exclusions

Phase 1 excludes:

- autonomous LIVE trading;
- physical real-money broker submission;
- physical broker OCO or protective-order submission;
- destructive architecture consolidation;
- deletion of legacy or duplicate-looking modules;
- TradingView implementation;
- new market-data providers;
- new intelligence, ML, or adaptive-learning functionality;
- product, commercial, membership, or billing expansion;
- general assistant or Jarvis expansion;
- voice, mobile, Telegram, WhatsApp, or email expansion;
- production deployment;
- production monitoring and alerting.

### 17.2 Phase 1 entry gate

Phase 1 entry requires:

- Phase 0 remains certified;
- current repository and tests are available;
- the application entry point is identified or recorded as unresolved;
- LIVE and physical broker execution remain disabled;
- no critical safety defect is knowingly bypassed;
- relevant files are inspected;
- ambiguity is recorded rather than guessed;
- scope remains limited to architecture, ownership, characterization, and
  documentation;
- destructive consolidation is not authorized.

### 17.3 Phase 1 exit gate

Phase 1 exit requires:

- a documented application entry point and startup path;
- a documented active runtime call graph;
- one documented canonical PAPER path;
- ownership for every canonical stage;
- separated admission, preparation, execution, and state mutation;
- explicit risk and financial-state authorities or recorded unresolved issues;
- account-switch characterization;
- documented lifecycle and recovery ownership;
- explicit recovery-or-block semantics;
- complete reviewed route and dashboard inventory;
- read-only characterization;
- authorization and account scope for mutating operations;
- PAPER/LIVE isolation evidence;
- compatibility classification;
- characterization coverage;
- an open-risk and evidence-limitations register;
- no claim that the broader PAPER MVP is approved.

### 17.4 Phase 1 safety and test gates

Phase 1 must preserve:

- zero execution side effects for rejected signals;
- fail-closed risk controls;
- centralized freshness and quote authority;
- no synthetic spreads;
- PAPER/LIVE separation;
- non-mutating read operations;
- account-switch containment;
- recovery-or-block semantics;
- unavailable physical broker protections;
- disabled autonomous LIVE execution.

Tests must cover rejected signals, stale data, unauthorized execution, PAPER
isolation, valid PAPER flow, duplicate requests, fill synchronization,
interrupted operations, repeated recovery, account switching, read-side safety,
authorization, and missing risk data.

---

## 18. HISTORICAL IDEAS, DEFERRED SCOPE, AND BLOCKED SCOPE

Historical ideas retained as `HISTORICAL_IDEA` or `DEFERRED` include:

- broader assistant platform;
- exact 15m/5m/1m historical workflow;
- historical API demonstrations;
- Telegram;
- WhatsApp;
- mobile;
- voice;
- general Jarvis assistant;
- Home Assistant;
- facial recognition and robotics;
- memberships;
- Basic and Premium packages;
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
- any path bypassing risk, authorization, freshness, account, or recovery
  controls.

---

## 19. CONFLICTS, SUPERSESSION, AND DUPLICATES

### Historical LIVE vision versus current policy

Classification: `CONFLICT`

Historical LIVE intent is preserved, but autonomous LIVE execution remains
blocked until a separate authorization and independent safety-validation phase.

### Historical demonstrations versus current proof

Classification: `CONFLICT`

Historical API demonstrations remain historical evidence. Current repository
code, tests, runtime composition, and operational evidence determine current
status.

### Historical account values versus runtime configuration

Classification: `SUPERSEDED`

Historical account values remain examples only. Runtime account configuration is
authoritative.

### Synthetic spread assumptions versus quote authority

Classification: `SUPERSEDED`

Synthetic quote and spread generation is prohibited.

### Repeated Phase 0 closure statements

Classification: `DUPLICATE`

Repeated statements across documentation preserve traceability but do not
represent separate requirements.

### Duplicate-looking architecture modules

Classification: `NEEDS_VERIFICATION`

Modules must not be deleted or merged without import, call-graph,
compatibility, persistence, and regression evidence.

---

## 20. CURRENT NEXT ACTION

The current next action is:

```text
Phase 1 entry-gate verification
→ repository/runtime characterization
→ runtime call-graph inventory
→ canonical ownership maps
→ characterization-test inventory
→ Phase 1 evidence-package review
```

This action does not authorize:

- production-code expansion;
- destructive consolidation;
- LIVE execution;
- physical broker submission;
- product expansion.

---

## 21. CURRENT MEMORY STATUS

Status:

`HISTORICAL CONSOLIDATION COMPLETE; PHASE 1 CORE RELIABILITY DEFINED`

The controlled PAPER product remains a bounded target whose complete end-to-end
runtime composition, synchronization, operational readiness, and MVP approval
require additional current evidence.

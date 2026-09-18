# Phase 2 PAPER MVP remaining-gap audit — V9

Baseline: `25280bdfbc01156cc027b5dd1955eb20107317a5`, synchronized branch
`refactor/backend-architecture`. Phase 1 remains **CLOSED**. The PAPER MVP is
**not ready**. This package supplies an evidence inventory, executable boundary
characterizations and a dependency-ordered implementation plan; it changes no
production behavior. LIVE execution remains disabled.

## Scope and counting

The authoritative MVP exit criteria are the roadmap's section 12: canonical
runtime, accepted and rejected PAPER integration, isolation, risk, financial
synchronization, idempotency, recovery, authorization, regression and operational
startup-to-PAPER smoke. DATA/INTEL/SIGNAL/PROD/OPS requirements determine the minimum
usable market-to-dashboard product around those contracts. Historical Jarvis,
mobile, commercial, external AI and advanced-autonomy ideas are excluded.

The companion machine inventory is
`backend/tests/phase2_mvp_capability_inventory_v9.json`. It records every
capability's owner, implementation/integration/test/E2E status, mandatory flag,
blocker, dependencies and source evidence. It also records each transition,
input provenance class, all twelve acceptance steps and follow-up package gates.

Thirty capability groups were evaluated: **24 mandatory**, **6 post-MVP**.
Fourteen mandatory groups have certified operational/component boundaries;
four need integration or integrated proof; six are partial. None is classified
missing or externally blocked. Completion is **floor(14 / 24 × 100) = 58%**.
This is a capability count, not a percentage of engineering effort or a claim
that 58% of a live product workflow passes. Ten mandatory groups remain open:
**4 P0, 5 P1, 1 P2**. Several share a root cause, so the plan uses three packages.

`CLOSED_CERTIFIED` applies only to the named capability boundary. For example,
the PAPER lifecycle accepts a manually supplied valid request, but that does not
prove the application's intelligence generated it from external market data.
The count bucket `IMPLEMENTED_NEEDS_INTEGRATION` combines the two allowed
implemented-but-unintegrated/unproven statuses. All other buckets are disjoint.

## Verified gaps and actual call path

1. **Operational candle ingestion stops before intelligence.** The coordinated
   ASGI app exposes its canonical `PositionManagerV2`; both `/market/webhook`
   and `/market/analyze` require the incompatible legacy `PositionManager`.
   `get_position_manager` returns `503 legacy_position_manager_unavailable`.
   The webhook performs this lookup before `LiveCandleStore.add`. The V9 tests
   reproduce both barriers, verify no candle is stored and compare unchanged
   economic state and fills. This is the safe unavailable behavior certified in
   Phase 1, not a newly introduced execution regression.
2. **The candidate/account bridge is incomplete.** `LiveMarketAnalysisService`
   has a real pipeline and calls `TradeLifecycleServiceV2.submit_signal`, but its
   generated risk context omits `account_id` and `profile_name`, required for
   coordinated account admission. Connecting only the candle route would not
   establish the complete operational path. Source identity, generation and
   command ownership need to accompany a generated candidate.
3. **Browser authorization is incomplete.** Public dashboard and switch-context
   reads work. The existing `dashboardApi.ts` uses fixed localhost URLs and
   supplies no administrative authorization for the protected switch mutation.
   The actual backend rejects that mutation with 401. The browser opens a bare
   WebSocket URL, whereas the backend requires `X-ARMS-ADMIN-TOKEN` before accept;
   the matching unauthorized handshake closes with 1008. A browser-compatible
   session/proxy/ticket boundary needs deliberate integration. Removing backend
   authorization or placing a server secret in a public bundle is not a repair.
4. **Operational inputs and complete smoke evidence are missing.** Quote and
   price POST endpoints accept explicit application inputs, but no concrete
   external provider is configured. The provider protocol supplies a last price,
   not a full bid/ask plus OHLC stream. Certified calendar/news loaders require
   supplied dated files. A real maintained source, account configuration, browser
   authorization and one reproducible public-input/restart scenario are needed.
5. **Validation claims require provenance.** App walk-forward factories pin
   `data/backtest/nq_history.csv`; certification registration uses `STR-001`.
   The test named `test_strategy_certification_pipeline_real_e2e_v2.py` includes
   fake walk-forward and Monte Carlo pipelines. These are legitimate component
   tests, not proof of arbitrary dataset/strategy certification. Minimal source
   and candidate provenance is mandatory; a research platform is not.

```text
explicit bid/ask -> authenticated quote endpoint -> canonical freshness    CONNECTED
OHLC -> coordinated webhook -> candle store                              DISCONNECTED
candles -> EMA/RSI/ATR/structure -> intelligence                          TEST/COMPONENT
intelligence -> generated account-bound candidate                        DISCONNECTED
manual canonical request -> risk/news/hours/admission -> PAPER fill       CONNECTED
fill -> position/protection -> portfolio/account/PnL -> journal           CONNECTED
canonical state -> dashboard API / authorized backend WebSocket          CONNECTED
dashboard API -> mandatory browser product                              PARTIAL
authorized WebSocket -> native browser client                            DISCONNECTED
financial state -> durable snapshot -> safe restart/recovery             CONNECTED
```

The manifest lists every mandatory transition individually. The complete PAPER
E2E path is **RED**, because public candle input cannot reach intelligence and
the browser transport is unfinished. It is not repaired by manually injecting
stores, constructing an approved signal, or displaying advisory demo metrics.

## Minimum intelligence, news and research scope

The smallest already-designed stack is the live analysis service's
`BacktestMarketStage` over supplied candles, `IndicatorStage` (EMA 50, RSI 14,
ATR 14), `SmartMoneyStage` (structure, BOS/CHOCH, liquidity), `IntelligenceStage`,
risk/decision stages and the existing v2 confluence/probability/plan/validator/
signal delegates. The service requires at least 50 candles. Reuse those owners;
do not introduce a parallel strategy or relax configured probability gates.

Exchange market hours, holiday/special-session coverage, high-impact-news vetoes,
current quote freshness and all account/risk restrictions are mandatory.
Unknown or expired coverage must block. Regional Asia/London/New York labels
and session-high/low overlays are historical product ideas rather than an
explicit MVP exit gate. FVG detection already exists in `SmartMoneyEngineV2.detect_fvg` and confluence.
Extra experimental FVG/multi-timeframe/adaptive functionality must not become
a new MVP requirement; configured current checks still apply.

CSV replay/backtesting exists with isolated ledgers. Walk-forward, Monte Carlo,
scoring and registry infrastructure exist, but the roadmap's MVP exit list does
not require a research UI or a strategy-certification activation gate. No such
operational activation guarantee is certified here. If research results are
shown or used, dataset/strategy traceability and honest status are mandatory.
On-demand daily PnL and journal views are required; scheduled daily report
delivery is post-MVP. Physical broker orders/protections are excluded.

## Real inputs versus fixtures

The V9 tests use real coordinated application owners and isolated PAPER account
configuration. Market data is supplied through HTTP; no production owner,
approval decision, market store or financial record is patched. They prove
quote ingress, safe candle/analyze rejection, protected-mutation/socket denial,
and matching authorized HTTP/socket financial projections. Snapshot timestamps
are compared separately because two reads occur at different times.

Prior positive V8.1 lifecycle evidence deliberately uses a fixed test clock,
test-certified calendar/news files and explicit quote publication. It remains
valid evidence of admission and execution, but is not operational feed proof.
PAPER broker simulation is intentional and acceptable. Browser advisory
`getAIDecision` uses fixed metrics, and some intelligence widgets disclose
unavailable/demo state; neither is the operational signal source.

No paid feed, third-party credential or external account was selected, accessed
or modified. Therefore `BLOCKED_EXTERNAL=0` describes the current audit, not a
promise that a future vendor integration needs no credentials. Existing HTTP
ingress and local CSV replay are the available local boundaries. CSV replay
alone does not satisfy the operational live-data path.

## Startup and operator experience

Current supported commands, from the repository root, after approved local
configuration and dependency installation:

```powershell
python -m uvicorn backend.api.asgi:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd C:\Development\ARMS-AI\frontend
npm run dev
```

For a frontend production build, the existing scripts are `npm run build` then
`npm run start`. Browse `/dashboard-v2`; `/` is a separate analytics surface.
This audit ran the declared lint/build and existing Node tests, and starts the
real ASGI owners through TestClient. It does not claim a complete two-process
browser/PAPER smoke passed. `frontend/README.md` is generic Next.js guidance.

Required API policy environment names are `ARMS_MAXIMUM_QUOTE_AGE_SECONDS`,
`ARMS_MINIMUM_REWARD_RISK_RATIO`, `ARMS_MINIMUM_STOP_POINTS`,
`ARMS_MAXIMUM_STOP_POINTS`, `ARMS_MAXIMUM_SPREAD_POINTS`,
`ARMS_MINIMUM_ATR_POINTS`, `ARMS_MINIMUM_A_PLUS_PROBABILITY`,
`ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE`, `ARMS_MAXIMUM_SIGNAL_AGE_SECONDS`, and
`ARMS_MAXIMUM_OPEN_POSITIONS`. Values must be explicitly reviewed operator
policy; the test POLICY is not a deployment recommendation. Optional policy
overrides are defined and validated in `APISettings`.

Set separate local admin/webhook authorization configuration, plus actual
`ARMS_CERTIFIED_MARKET_HOURS_PATH` and `ARMS_CERTIFIED_ECONOMIC_NEWS_PATH` files.
Do not publish secret values. Without admin configuration privileged operations
are unavailable; without certified current market permission submission denies.
`backend/config/accounts.json` selects the account profile. The ASGI
`ARMS_RUNTIME_STATE_PATH` defaults to `data/runtime/runtime-state-v2.json` and
derives account namespaces and catalog beside that location. Keep the namespace
writable and exclusive to the owning process. Canonical recovery uses durable
JSON; a separate database server is not required for this PAPER core.

Provide actual bid/ask to `/market/quote` using webhook authorization, dated
prices to `/api/v3/dashboard/market-price` using administrative authorization,
and, after package 1, dated OHLC through the canonical candle ingress. Never
fabricate a spread from candles. Maintain real calendar/news coverage and make
expiry visible. The existing `scripts/live_http_smoke_v2.py` constructs a signal
and predates current authorization/account/market setup; it is not the current
MVP acceptance command. These engineering-only setup gaps belong to package 3.

## Executable acceptance specification

The manifest defines twelve ordered actions and assertions: start, readiness,
public market input, real intelligence, unsafe rejection, generated valid
admission, one PAPER order/fill, exactly-once financial updates, journal,
browser dashboard, browser WebSocket and restart. Each points to current tests
and explicitly marks incomplete integration. Final release requires one scenario
joining them through application interfaces with traceable controlled inputs.
No xfail, skip or wholesale fake pipeline is used to disguise the missing path.

The new tests intentionally characterize current barriers. A future integration
package must update those characterizations and inventory together when replacing
503 with a working path; 503 is not the desired MVP acceptance criterion.

## Verification and scope

Current counts/results are stored in the manifest. Baseline backend: 5,508 passed,
0 failed, 1 unchanged skip. Frontend: lint passes with four existing unused-variable
warnings, production build passes, and all six existing Node tests pass. Audit
characterization: six tests pass. Final full backend: **5,514 passed, 0 failed,
1 unchanged skip**. The skip is the unregistered compatibility submit route in
`test_phase1_risk_authority_integration_v2.py`; canonical submission is covered.
Initial audit assertions were corrected after
observing that switch-context is public and snapshot timestamps differ; these
were audit assumptions, not production regressions.

Exact backend invocation installs the repository test POLICY then calls pytest
with `-q -p no:cacheprovider --tb=short`, selecting `backend/tests` for the full
gate and `backend/tests/test_phase2_mvp_acceptance_v9.py` for direct evidence.
Final affected regression: the V9 audit, original V8 acceptance and V8.1 runtime
admission modules pass **60/60** together. A restricted rerun first encountered
59 fixture setup errors because Windows denied pytest temporary-directory
access (one inventory test passed); isolated reproduction confirmed WinError 5.
The same selection with required filesystem access passed all 60. This is
environment attribution, not a production patch or ignored test failure.

Frontend commands: `npm run lint`, `npm run build`, and
`node --test src/lib/dashboardApi.test.mjs`, all from `frontend`.
Evidence is under `C:/Users/THECRA~1/AppData/Local/Temp/arms-mvp-v9-yv_am1b9/`.

No safely isolated production fix was identified: the remaining blockers require
coordinated market/intelligence, browser authorization or operational integration.
V9 closes the inventory/test-plan/runbook documentation gap only. It preserves
Phase 1 certification and all unrelated untracked files. Exact changed-file
scope, final full regression, compile, diff and delivery checks are recorded
before the authorized audit-only commit.

## Capability inventory and priority

The full per-dimension statuses, blockers, owners and source paths are in the
machine inventory; this table is its concise review projection.

| ID | Capability | Mandatory | Status | Open priority |
| --- | --- | --- | --- | --- |
| MVP-001 | Application startup and PAPER readiness | YES | CLOSED_CERTIFIED | NONE |
| MVP-002 | Account profiles and identity | YES | CLOSED_CERTIFIED | NONE |
| MVP-003 | Account switching and containment | YES | CLOSED_CERTIFIED | NONE |
| MVP-004 | Quote ingress, availability and freshness | YES | CLOSED_CERTIFIED | NONE |
| MVP-005 | Operational candle ingestion and feed source | YES | PARTIAL | P0 |
| MVP-006 | Minimum indicators and market structure stack | YES | IMPLEMENTED_NOT_INTEGRATED | P0 |
| MVP-007 | Confluence, probability and decision evaluation | YES | IMPLEMENTED_NOT_INTEGRATED | P0 |
| MVP-008 | Canonical candidate to account-bound submission | YES | PARTIAL | P0 |
| MVP-009 | Certified market-hours and high-impact-news veto | YES | CLOSED_CERTIFIED | NONE |
| MVP-010 | Operational calendar/news inputs and refresh procedure | YES | PARTIAL | P1 |
| MVP-011 | Account risk, sizing and precedence | YES | CLOSED_CERTIFIED | NONE |
| MVP-012 | Trade validation and runtime admission | YES | CLOSED_CERTIFIED | NONE |
| MVP-013 | PAPER order preparation and fills | YES | CLOSED_CERTIFIED | NONE |
| MVP-014 | Positions, lifecycle and logical protections | YES | CLOSED_CERTIFIED | NONE |
| MVP-015 | Balance, equity, PnL and exactly-once financial updates | YES | CLOSED_CERTIFIED | NONE |
| MVP-016 | Durable journal and trade history | YES | CLOSED_CERTIFIED | NONE |
| MVP-017 | Authoritative dashboard backend projections | YES | CLOSED_CERTIFIED | NONE |
| MVP-018 | Browser HTTP authorization and endpoint configuration | YES | PARTIAL | P1 |
| MVP-019 | Usable mandatory dashboard views and candidate state | YES | PARTIAL | P1 |
| MVP-020 | Authorized backend WebSocket projection and retirement | YES | CLOSED_CERTIFIED | NONE |
| MVP-021 | Browser WebSocket authentication and reconnection | YES | IMPLEMENTED_NOT_INTEGRATED | P1 |
| MVP-022 | Durability, pending reconciliation and restart recovery | YES | CLOSED_CERTIFIED | NONE |
| MVP-023 | Reproducible operator startup-to-PAPER acceptance | YES | IMPLEMENTED_NEEDS_E2E_PROOF | P1 |
| MVP-024 | Candidate and validation provenance before release | YES | PARTIAL | P2 |
| MVP-025 | Offline CSV backtesting research | NO | POST_MVP | POST_MVP |
| MVP-026 | Walk-forward, Monte Carlo and strategy certification activation | NO | POST_MVP | POST_MVP |
| MVP-027 | Automated daily summary delivery | NO | POST_MVP | POST_MVP |
| MVP-028 | Asia/London/New York session overlays and session extremes | NO | POST_MVP | POST_MVP |
| MVP-029 | Experimental FVG, extra multi-timeframe and adaptive AI features | NO | POST_MVP | POST_MVP |
| MVP-030 | Vendor-specific paid feed, LIVE, mobile and commercial expansion | NO | POST_MVP | POST_MVP |

## Twelve-step release acceptance plan

Run sequentially with a single isolated PAPER account, real application owners
and traceable dated controlled input. Existing component certificates do not
substitute for the joined browser scenario. The JSON identifies runnable current
test evidence and the status of each step.

| Step | Action | Required assertion |
| --- | --- | --- |
| 1 | Start backend ASGI with isolated account config and explicit policy; start frontend using declared scripts. | Health endpoint 200; configuration errors fail startup; no trade on startup. |
| 2 | Read startup/current account report. | Exactly one published PAPER runtime, current account/profile/generation, no LIVE adapter. |
| 3 | POST dated bid/ask quote and OHLC candles through authenticated application ingress, including malformed/stale/duplicate/out-of-order negatives. | Accepted source reaches the same quote/candle owners used by admission; no synthetic spread or store injection. Current candle 503 is an explicit blocker. |
| 4 | Run real indicators/structure/confluence/probability/plan over supplied candles through the supported command boundary. | Candidate or explicit rejection with source, symbol, timestamps, strategy/config identity; no mocked approval or fabricated confidence. |
| 5 | Exercise missing/stale/news-blocked/account-blocked/risk-rejected candidate variants. | Zero prepare/broker/fill/position/protection/financial side effects; stronger veto cannot be overridden. |
| 6 | Supply a genuinely qualifying dated input sequence and certified hours/news coverage. | Generated candidate carries canonical account/profile/generation and reaches existing admission; do not replace it with a prebuilt approved signal. |
| 7 | Execute admitted PAPER request once and repeat its identity. | One canonical order/fill; duplicate request creates no second fill; PAPER connector only. |
| 8 | Publish operational price through canonical price ingress and exercise exit/partial outcome. | Portfolio/account/PnL/protection synchronize exactly once; no direct ledger edits. |
| 9 | Read journal/history through application API. | Records correlate candidate/request/order/fill/position and do not imply execution for a rejected candidate. |
| 10 | Use the actual browser dashboard under supported authorization. | Account, balance/equity, risk, position, candidate, market availability, PnL and journal match canonical API state; empty/blocked data is explicit. |
| 11 | Subscribe with supported browser authentication; trade/update/switch account. | Browser sees matching snapshot/events and retire/reconnect behavior, no stale-account projection and no trading caused by reads. |
| 12 | Stop/restart against the same isolated durable namespace; include pending/crash cases. | Reconstructed identity, positions, journal and financial totals match; no resubmission; unknown/corrupt state blocks; market permission must become fresh again. |

## Dependency-ordered implementation packages

These are proposed follow-up scopes, not production changes made in V9.
No calendar estimates are implied.

### 1. PHASE2_CANONICAL_MARKET_TO_CANDIDATE

Objective: Connect authenticated quote/candle/price ingestion and real minimum intelligence to a traceable account-bound candidate while keeping all existing admission vetoes.

Dependencies: Phase 1 closed.

Estimated scope: Cross-module integration, not an audit-local patch.

Expected files/areas: `backend/api/routers/market.py`, `backend/services/live_market_analysis_service.py`, `backend/signals/signal_generator_v2.py`, `backend/services/live_candle_store.py`, `backend/market_data`, `backend/tests`.

Acceptance gate: Public controlled dated inputs produce a real candidate; account/profile/generation and source identity preserved; missing/stale/invalid/duplicate/out-of-order data cannot trade; approved candidate fills exactly once; all Phase 1 contracts and full backend green.

### 2. PHASE2_AUTHORIZED_PAPER_DASHBOARD

Objective: Connect required browser account/risk/position/PnL/journal/candidate views and WebSocket through supported authorization.

Dependencies: PHASE2_CANONICAL_MARKET_TO_CANDIDATE.

Estimated scope: Backend/browser authentication transport and frontend integration; no redesign.

Expected files/areas: `frontend/src/lib/dashboardApi.ts`, `frontend/src/app/dashboard-v2/page.tsx`, `frontend/src/components/dashboard-v2`, `backend/api/dashboard_websocket_api_v2.py`, `backend/security`, `browser integration tests`.

Acceptance gate: Real browser authenticates without embedding server secrets; HTTP/WS account switch and retirement work; unavailable states remain explicit; reads cannot trade; lint/build/tests and backend all green.

### 3. PHASE2_PAPER_MVP_OPERATIONAL_ACCEPTANCE

Objective: Finish certified input maintenance, provenance, reproducible startup and the single public-input/browser/restart acceptance scenario.

Dependencies: PHASE2_CANONICAL_MARKET_TO_CANDIDATE, PHASE2_AUTHORIZED_PAPER_DASHBOARD.

Estimated scope: Operational configuration/runbook, provenance assertions and integrated smoke.

Expected files/areas: `backend/config/api_settings.py`, `certified market/news lifecycle configuration`, `scripts`, `docs`, `backend/tests`, `frontend integration tests`, `validation provenance boundaries`.

Acceptance gate: All 12 acceptance steps and mandatory transitions connected with real owners; supplied market inputs traceable and current; news/holiday unknowns deny; crash/restart restores exact financial state; no fake certification claims; zero backend failures and frontend gates green.

## Exact change justification

- `backend/tests/test_phase2_mvp_acceptance_v9.py`: six real-owner boundary
  characterizations and inventory integrity checks.
- `backend/tests/phase2_mvp_capability_inventory_v9.json`: authoritative capability,
  transition, source, acceptance, package and test-result inventory.
- This report: root causes, scope decisions, commands, limitations and review tables.
- `docs/master/ARMS_AI_MASTER_MEMORY.md`: current Phase 2 evidence pointer.
- `docs/master/ARMS_AI_MASTER_ROADMAP.md`: next dependency-ordered packages.
- `docs/master/ARMS_AI_REQUIREMENTS_MATRIX.md`: Phase 2 capability/status authority
  while preserving the closed Phase 1 requirement rows.
- `docs/master/ARMS_AI_DECISION_LOG.md`: DEC-0020 records this audit disposition.

Safety evidence: rejected input cannot create orders/fills/positions or mutate
financial state; missing market permission denies; authenticated backend
projections do not trade; unauthorized browser operations remain denied. The
full backend regression retains account isolation, exactly-once financial
updates, durable recovery and the original V8 admission rejection tests.

Remaining limitation: no complete public-market-to-browser/restart operational
MVP smoke has passed. The next action is package 1 above.

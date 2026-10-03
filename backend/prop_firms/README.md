# Prop firm rule engine v1

This package is a pure domain evaluator. It imports no FastAPI, broker, order, PAPER, or LIVE execution code. An `eligible` result describes only compliance with a selected profile for the requested assessment; it is never authorization to trade, withdraw, or mutate an account. Callers must separately enforce all execution and authorization gates.

Profiles use explicit `Decimal` values and timezone-aware effective dates. No current firm's limits are included. `AccountProgram.select` requires one exact active profile for firm/program, account size, stage, and time; zero or multiple matches raise an error. The SHA-256 `config_hash` covers every profile field other than the hash itself, including source and effective dates. Profiles and snapshots are immutable. Version is a human-supplied label; changing any rule changes the hash even if the label stays the same.

## Snapshot contract

`starting_balance` is the account's original balance. `current_balance` is cash balance after realized PnL and withdrawals; `current_equity` also includes open PnL. `daily_pnl` is the firm's applicable loss measure for the current trading day, supplied by the caller. `total_profit` is cumulative gross profit before withdrawals; `withdrawals` is cumulative paid-out profit, so available payout profit is their difference. `highest_equity` is the intraday equity high since account inception; `highest_end_of_day_balance` is the highest closed-day balance since inception. They must include the starting balance. The caller must provide a coherent snapshot and the correct firm's trading-day boundaries. The engine does not reconstruct history, infer a missing high, or substitute simulated data.

## Drawdown semantics

- `STATIC`: floor is starting balance minus maximum loss; compare the explicitly configured balance or equity basis.
- `TRAILING_INTRADAY`: floor is highest intraday equity minus maximum loss; compare the configured basis.
- `TRAILING_END_OF_DAY`: floor is highest closed-day balance minus maximum loss; compare the configured basis.
- `BALANCE_BASED`: fixed starting-balance floor; compare current balance.
- `EQUITY_BASED`: fixed starting-balance floor; compare current equity.
- `NONE`: explicitly disables this rule.
- Optional `floor_cap` caps an increasing floor at the given absolute balance (`min(calculated_floor, floor_cap)`).
- Remaining drawdown is observed value minus floor. Zero or negative remaining breaches. A missing required field or inconsistent starting/high-water value also breaches, with an explicit reason.

The static, balance-based, and equity-based models differ by the permitted comparison basis. No trailing behavior is implied by `BALANCE_BASED` or `EQUITY_BASED`.

## Other rules

Daily loss used is `max(0, -daily_pnl)`; zero remaining breaches. Open contract count may equal the cap (zero new capacity), while an existing count above the cap breaches. An optional traded contract cap checks cumulative traded contracts from the snapshot.

Consistency is the configured best-day profit divided by either total profit or realized PnL. Its denominator must be positive and at least the configured minimum. A policy explicitly chooses whether equality at the configured maximum passes or breaches. Disabled policies have no effect.

Account evaluation aggregates active drawdown, daily loss, contract, consistency, minimum trading days, and profit-target conditions. Payout evaluation includes account conditions plus the configured payout gates. The requested payout must not exceed available profit. Minimum balance and drawdown buffer are checked *after* subtracting the requested amount; the buffer uses the drawdown comparison basis. A prior payout cooldown requires an explicit count and, when count is positive, the last payout time. No payout state is changed.

Missing data produces `eligible=False` and stable reason codes. Invalid configuration, nonfinite money, floats, naive timestamps, and negative counts are rejected at construction. This foundation does not encode any Topstep, Apex, TakeProfitTrader, or Lucid values. Source-backed profiles and their firm-specific definitions are separate work.

## Domain extension (R24B1)

The V1 entry points retain their original meaning for V1 profiles. If a profile uses any V2-only policy, V1 account and payout evaluators return `UNSUPPORTED_POLICY_USE_V2` with `eligible=False`. Use `evaluate_account_v2`, `evaluate_drawdown_v2`, and `evaluate_payout_v2` for extended profiles. The V2 result has independent `account_valid`, `account_failed`, `trading_allowed_now`, `stage_objective_met`, and `payout_eligible` dimensions. None of these values grants execution authority.

Every V2 rule yields an immutable `RuleOutcome` with a scope and one of `PASS`, `SESSION_BLOCKED`, `TRADING_BLOCKED`, `ACCOUNT_FAILED`, `OBJECTIVE_PENDING`, `WARNING`, `NOT_APPLICABLE`, or `INCOMPLETE_DATA`. A temporary session block or trading block prevents trading now but does not fail the account. A hard breach fails the account. V2 snapshots must explicitly state whether the account failed previously; missing history blocks evaluation, and a previous hard failure remains failed even if current prices recover. An objective pending prevents stage completion but does not itself stop trading. Warnings are advisory. Missing required inputs produce `INCOMPLETE_DATA` and fail closed for the affected decision. Payout evaluation never passes while any required rule input is incomplete.

A daily loss policy explicitly chooses `SESSION_BLOCK`, `ACCOUNT_FAIL`, `WARNING_ONLY`, `OBJECTIVE_ONLY`, or `NOT_APPLICABLE`. A session block requires a matching `session_id` and `daily_pnl_session_id`, plus a future boundary supplied by the caller. Its configured reset boundary is either `SESSION_END` or `TRADING_DAY_END`. The engine reports `reset_at` but does not reset state; the caller supplies the next session's snapshot. A session-block policy also requires explicit prior block state and its session ID. An active block stays active for that session even if later PnL rises; a new session ID ends that prior block. Missing block history fails closed.

A profile may explicitly allow a zero starting balance. Negative starting balances remain invalid. Drawdown reference updates are independent of breach checks: the reference may be fixed at the start, use intraday highest equity, or use highest closed-day balance; the breach basis may be balance, equity, or the lower of both. A floor cap limits upward trailing. An optional payout-count transition fixes the floor after the configured event. An optional floor lock takes the greater of the calculated floor and a supplied prior floor. Missing lifecycle facts, prior floor, or high-water data produce `INCOMPLETE_DATA`. The engine never reconstructs prior state or changes the snapshot.

For weighted exposure, the profile contains a maximum in `Decimal` units, instrument-specific weights, optional product-group weights, and trusted instrument-to-group mappings. Instrument weight takes precedence. Group weights apply only to instruments mapped by the profile; a caller-provided group must match that mapping. Unknown products fail closed. Snapshot quantities are nonnegative absolute open quantities. No mini/micro ratio or product exception is built into the engine.

A payout-cycle snapshot carries cycle identity, prior payout count and time, profits and days since the previous payout, cycle start, cumulative withdrawals, and optional requested amount. The payout policy can set minimum winning/trading days, minimum cycle profit, minimum request, balance or available-profit percentage basis, fixed caps, buffer, waiting period, and sorted payout-count tiers. Consistency can be configured for stage, payout cycle, or both. The engine only evaluates supplied cycle facts. **NO PAYOUT ACTION, NO ACCOUNT MUTATION, NO CYCLE MUTATION.**

V2 profiles may also define scaling tiers resolved from the supplied prior end-of-day balance. A resolved tier can override the active exposure cap and daily loss limit. Evaluation access periods require an explicit account start time. Rolling inactivity rules require an exact caller-supplied window, qualifying-day count, and profit threshold once the first window matures. Payout rules may require qualifying days at an exact threshold, cap the number of prior payouts, require no open contracts or working orders, and report the configured trader profit fraction. Profit-split reporting never changes eligibility or performs a withdrawal. Missing or mismatched lifecycle evidence fails closed; the engine never derives it from trades.

Profiles can include immutable source evidence with URL, title, retrieval time in UTC, optional effective dates, heading, normalized hash, and temporary-review markers. Review status is `CURRENT_VERIFIED`, `STALE_REVIEW_REQUIRED`, `SOURCE_CONFLICT`, `SOURCE_UNAVAILABLE`, or `INCOMPLETE`. An explicit review deadline can make a current review stale at evaluation time; age alone does not. Callers can require verified-current sources. Conflicting, unavailable, or incomplete sources always fail closed. Source metadata and all extension policies participate in the profile's configuration hash.

The package performs no network, database, broker, order, position, PAPER, LIVE, or payout action. Source verification, account snapshot reconstruction, and execution authorization belong to separate components.

## Topstep profiles (R24B2A)

`topstep_profiles.py` contains source-backed profiles reviewed on 2026-10-03. Trading Combine profiles cover the published 50K, 100K, and 150K sizes, profit targets, two-day objective, 55% consistency target, end-of-day maximum loss limit, 10:1 mini/micro exposure, and optional daily loss limit variants. Contract-limit breaches use `TRADING_BLOCKED`; unsupported product mappings use `INCOMPLETE_DATA`. Neither result creates an account failure unless a separately configured hard rule is breached.

Express Funded Account Standard and Consistency profiles are deliberately `INCOMPLETE`. They model the zero starting balance, end-of-day maximum loss behavior, post-first-payout zero floor, optional daily loss limit, payout cycles, payout caps, 50% balance cap, minimum payout, and 40% consistency path where applicable. The official scaling table is image-only in the reviewed source, so contract evaluation always returns `SCALING_PLAN_TIER_DATA_UNAVAILABLE` and blocks trading and payout eligibility. The engine does not guess or transcribe the missing tiers.

Live Funded and Pro Account are separate support records with explicit unsupported reasons. They do not create evaluable profiles. The limited-time doubled payout-cap variant is opt-in, marks its evidence as temporary and review-required, and has a one-day source review deadline.

## Apex profiles (R24C)

`apex_profiles.py` models the current EOD Drawdown and Intraday Trailing products introduced on 2026-03-01. Evaluation profiles cover 25K, 50K, 100K, and 150K sizes, published targets and drawdowns, 30-day access, fixed 10:1 mini/micro exposure limits, the EOD daily session loss limit, and the absence of that limit in Intraday evaluations. Rithmic and WealthCharts evaluation floors cap at the target balance; Tradovate remains uncapped as documented. Contract excess blocks trading without marking an account failure.

Performance profiles model dynamic contract and daily-loss tiers from prior EOD balance, the starting-balance-plus-$100 drawdown cap, the rolling 30-day activity requirement, five payout-qualifying days, strict-under-50% payout consistency, the $500 minimum, safety-net balance, six-payout maximum, and payout-number caps. The 50K performance profiles are `SOURCE_CONFLICT` and therefore fail closed because the official scaling and daily-loss pages disagree at the 5,999/6,000 boundary. No value is silently chosen to authorize activity.

Legacy products remain a separate, unimplemented support record. Current-product profiles never stand in for legacy accounts. All Apex outcomes remain read-only policy evaluations and provide no trading or payout side effect.

## TakeProfitTrader profiles (R24D)

`takeprofittrader_profiles.py` keeps Test, PRO, and PRO+ distinct across the published 25K, 50K, 75K, 100K, and 150K sizes. Test profiles model the three-day objective, strict-under-50% consistency, profit targets, static full-size 10:1 mini/micro limits, no daily loss limit, and the EOD drawdown that locks at starting balance. PRO profiles model the intraday drawdown, no daily loss or funded consistency rule, day-one active-account withdrawals above the buffer, an 80% trader share, and the flat-account withdrawal requirement. The separate PRO account-closure buffer route is unsupported.

PRO+ is represented only as a read-only `LIVE` policy profile. It models the verified EOD drawdown, absence of a payout buffer, 90% trader share, and no daily loss limit. It contains no broker adapter, activation, order route, or LIVE authorization.

All three stages are deliberately `INCOMPLETE`. Test still needs explicit approved-hours and counter-position snapshot semantics. PRO and PRO+ additionally need aligned Sunday-Friday weekly activity, dynamic prohibited-news state, and price-limit state. The verified numeric outcomes remain visible, while source status prevents `account_valid`, `trading_allowed_now`, or `payout_eligible` from becoming true. A discretionary PRO-to-PRO+ transition is metadata only.

## Profile registry (R25A)

`profile_registry.py` provides an immutable temporal registry over all normalized firm profiles. Resolution uses exact firm, program, stage, account size, effective timestamp, and optional version. Ambiguous variants require the caller to supply the exact version. Overlapping windows for the same version are rejected when the registry is constructed.

`resolve_profile` accepts only `CURRENT_VERIFIED` by default. Inspection of incomplete, conflicting, unavailable, or stale profiles requires the caller to pass `required_source_status=None`; the returned `ResolvedProfile` still includes the actual status. A profile without source review metadata is treated as `INCOMPLETE`. Listing and status methods always calculate status at the supplied timezone-aware timestamp and never relabel an expired review as current.

The registry is read-only. It selects configuration and performs no account, payout, PAPER, LIVE, broker, position, or order action.

## Identified account snapshot (R25B)

`PropFirmAccountSnapshot` binds an immutable `AccountSnapshot` to account ID, firm, program, stage, account size, exact profile version, capture time, data source, and an explicit simulated-data flag. It exposes balance, equity, realized and unrealized PnL, daily PnL, high-water marks, open exposure, trading and winning days, best day, payout-cycle profit, hard-breach state, and session-block state without recalculating or substituting values.

The wrapper requires its stage and capture time to match the nested rule state. Missing optional risk values remain `None` so evaluation fails closed. A deterministic SHA-256 content hash covers identity, provenance, and every nested state field. Constructing or reading a snapshot performs no broker, account, order, payout, PAPER, or LIVE action.

## Multi-account evaluator (R25C)

`evaluate_accounts` resolves and evaluates an immutable tuple of heterogeneous identified snapshots independently. Each result reports account validity, current trading state, objective and payout status, drawdown, daily loss, exposure, consistency, source status, blocking reasons, warnings, failures, metrics, and snapshot hash. A missing, ambiguous, incomplete, conflicting, unavailable, or stale profile blocks only its own account.

Current source status is required by default. Unverified analysis is an explicit option and the underlying rule engine still marks non-current source profiles invalid. Aggregate counts are diagnostics only; both account results and the aggregate hard-code `execution_authorized=False`. This module imports no broker, order, PAPER, or LIVE execution component and performs no mutation.

## Read-only policy API (R25D)

`prop_firm_policy_api_v1.py` exposes four isolated operations: list temporal profile descriptors, resolve one exact profile, evaluate one identified snapshot, and evaluate multiple identified snapshots. Request schemas reject unknown fields, retain missing risk values, require snapshot identity and timestamps, and convert JSON into the immutable domain models. Monetary response values are encoded as decimal strings.

The API is evaluation-only. Its POST operations calculate diagnostics and do not create a resource or mutate state. The router has no broker, PAPER, LIVE, position, portfolio, account, payout, or journal dependency, and every evaluation response retains `execution_authorized=false`. It is intentionally not registered in the operational application; a future host can mount it only after choosing an explicit deployment and access boundary.

## Multi-account portfolio analytics (R26A)

`analyze_prop_firm_portfolio` projects immutable identified account snapshots and their canonical rule diagnostics into aggregate balance, equity, realized and unrealized PnL, drawdown utilization, daily-limit utilization, exposure, payout readiness, and account, firm, and stage distributions. It does not use the mutable execution `PortfolioManagerV2` as an analytics authority.

Missing monetary or exposure values are never replaced with zero. Each aggregate carries a known-data subtotal, the account IDs with missing values, and a complete total only when every snapshot supplied that value. Utilization is reported per account with explicit `AVAILABLE`, `NOT_APPLICABLE`, or `INCOMPLETE` status. The output and nested diagnostics hard-code `execution_authorized=False`; analysis performs no broker, PAPER, LIVE, position, payout, account, or journal action.

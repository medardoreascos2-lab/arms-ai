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

Consistency is the configured best-day profit divided by either total profit or realized PnL. Its denominator must be positive and at least the configured minimum. The fraction breaches only when above the configured maximum. Disabled policies have no effect.

Account evaluation aggregates active drawdown, daily loss, contract, consistency, minimum trading days, and profit-target conditions. Payout evaluation includes account conditions plus the configured payout gates. The requested payout must not exceed available profit. Minimum balance and drawdown buffer are checked *after* subtracting the requested amount; the buffer uses the drawdown comparison basis. A prior payout cooldown requires an explicit count and, when count is positive, the last payout time. No payout state is changed.

Missing data produces `eligible=False` and stable reason codes. Invalid configuration, nonfinite money, floats, naive timestamps, and negative counts are rejected at construction. This foundation does not encode any Topstep, Apex, TakeProfitTrader, or Lucid values. Source-backed profiles and their firm-specific definitions are separate work.

## Domain extension (R24B1)

The V1 entry points retain their original meaning for V1 profiles. If a profile uses any V2-only policy, V1 account and payout evaluators return `UNSUPPORTED_POLICY_USE_V2` with `eligible=False`. Use `evaluate_account_v2`, `evaluate_drawdown_v2`, and `evaluate_payout_v2` for extended profiles. The V2 result has independent `account_valid`, `account_failed`, `trading_allowed_now`, `stage_objective_met`, and `payout_eligible` dimensions. None of these values grants execution authority.

Every V2 rule yields an immutable `RuleOutcome` with a scope and one of `PASS`, `SESSION_BLOCKED`, `ACCOUNT_FAILED`, `OBJECTIVE_PENDING`, `WARNING`, `NOT_APPLICABLE`, or `INCOMPLETE_DATA`. A temporary session block prevents trading now but does not fail the account. A hard breach fails the account. V2 snapshots must explicitly state whether the account failed previously; missing history blocks evaluation, and a previous hard failure remains failed even if current prices recover. An objective pending prevents stage completion but does not itself stop trading. Warnings are advisory. Missing required inputs produce `INCOMPLETE_DATA` and fail closed for the affected decision. Payout evaluation never passes while any required rule input is incomplete.

A daily loss policy explicitly chooses `SESSION_BLOCK`, `ACCOUNT_FAIL`, `WARNING_ONLY`, `OBJECTIVE_ONLY`, or `NOT_APPLICABLE`. A session block requires a matching `session_id` and `daily_pnl_session_id`, plus a future boundary supplied by the caller. Its configured reset boundary is either `SESSION_END` or `TRADING_DAY_END`. The engine reports `reset_at` but does not reset state; the caller supplies the next session's snapshot. A session-block policy also requires explicit prior block state and its session ID. An active block stays active for that session even if later PnL rises; a new session ID ends that prior block. Missing block history fails closed.

A profile may explicitly allow a zero starting balance. Negative starting balances remain invalid. Drawdown reference updates are independent of breach checks: the reference may be fixed at the start, use intraday highest equity, or use highest closed-day balance; the breach basis may be balance, equity, or the lower of both. A floor cap limits upward trailing. An optional payout-count transition fixes the floor after the configured event. An optional floor lock takes the greater of the calculated floor and a supplied prior floor. Missing lifecycle facts, prior floor, or high-water data produce `INCOMPLETE_DATA`. The engine never reconstructs prior state or changes the snapshot.

For weighted exposure, the profile contains a maximum in `Decimal` units, instrument-specific weights, optional product-group weights, and trusted instrument-to-group mappings. Instrument weight takes precedence. Group weights apply only to instruments mapped by the profile; a caller-provided group must match that mapping. Unknown products fail closed. Snapshot quantities are nonnegative absolute open quantities. No mini/micro ratio or product exception is built into the engine.

A payout-cycle snapshot carries cycle identity, prior payout count and time, profits and days since the previous payout, cycle start, cumulative withdrawals, and optional requested amount. The payout policy can set minimum winning/trading days, minimum cycle profit, minimum request, balance or available-profit percentage basis, fixed caps, buffer, waiting period, and sorted payout-count tiers. Consistency can be configured for stage, payout cycle, or both. The engine only evaluates supplied cycle facts. **NO PAYOUT ACTION, NO ACCOUNT MUTATION, NO CYCLE MUTATION.**

Profiles can include immutable source evidence with URL, title, retrieval time in UTC, optional effective dates, heading, and normalized hash. Review status is `CURRENT_VERIFIED`, `STALE_REVIEW_REQUIRED`, `SOURCE_CONFLICT`, or `INCOMPLETE`. An explicit review deadline can make a current review stale at evaluation time; age alone does not. Callers can require verified-current sources. Conflicting or incomplete sources always fail closed. Source metadata and all extension policies participate in the profile's configuration hash.

The package performs no network, database, broker, order, position, PAPER, LIVE, or payout action. It contains no firm-specific numbers. Source verification, account snapshot reconstruction, and execution authorization belong to separate components.

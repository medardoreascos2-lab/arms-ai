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

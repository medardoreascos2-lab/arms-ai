# Recovery consistency hardening (Phase 0.9B)

Invariant: **RECOVERY SUCCESS REQUIRES VERIFIED SEMANTIC CONSISTENCY.**

## AUTHORITATIVE STATE MATRIX

| State | Authority and required corroboration |
| --- | --- |
| Orders and fills | PAPER order/fill identifiers, side, symbol, execution mode, status, quantity and price; client-order index must refer back to the exact order. |
| Active exposure | PAPER positions, lifecycle and portfolio must have the same identities and remaining quantities. Entry fill/order/journal prices must agree. |
| Closed exposure | Terminal PAPER position (CLOSED, exit price, close reason, timestamp), entry/partial fills, terminal portfolio, journal and history must agree. Closed identities cannot reopen during PENDING reconciliation. |
| Point value | Configured PositionManager instrument resolver, cross-checked against persisted position point value. |
| Realized PnL | Mathematical value of demonstrated entry, partial exits and terminal exit, with direction, quantity and point value. Portfolio/account/journal/history are checked against this result. |
| Daily PnL | Realizations assigned by execution timestamps to AccountStateManager's Chicago trading day, plus explicitly recorded account risk adjustments. |
| Portfolio exposure | Portfolio open positions, cross-checked against PAPER/lifecycle. |
| Journal | Original audit identities and entry/exit/accounting evidence; journal alone cannot authorize a position or PnL. Original journal SL/TP are historical, not the authority for subsequent stop modifications. |
| SL/TP and OCO | Shared lifecycle, protection registry and OCO manager; current PAPER order/position SL/TP must match active lifecycle/portfolio/protection values. |
| Persistence | Checksummed checkpoint and operation-bound PENDING evidence. A checksum demonstrates byte integrity, not economic correctness. |

PaperExecutionEngine generates execution results; it is not a separate position
ledger. PAPER get_account() still reports connector starting balance; operational
balance/equity authority remains AccountStateManager and PortfolioManager.

## COMMITTED RECOVERY POLICY

Recovery requires a canonical PAPER broker, account-backed portfolio, journal,
and the same protection/OCO instances used by lifecycle. Missing or unshared
required authorities fail closed even for an empty recovery. Optional service
construction remains available outside durable recovery.

ExecutionStateStore invokes the shared `recovery_semantic_validation_v2` validator
on every validated checkpoint. It checks identifiers, order/fill status, quantity
conservation (including CLOSED positions), prices, side, instrument point value,
active protections and economic PnL. A new empty PAPER broker is reconstructed
only from complete persisted evidence. No missing position, fill, journal field
or PnL is inferred. There is no broker/snapshot merge policy.

The destination must contain no orders, fills, client-order index, active/closed
positions, history, journal, portfolio, protection/OCO or account execution
baseline. Existing daily adjustment evidence cannot be overwritten. Existing
structural/risk blocks cannot be removed. A repeated restore is allowed only
when its complete operational state still equals the expected snapshot.

An empty legacy snapshot may supply empty collections only when it contains no
activity and retains a valid account snapshot. Historical snapshots lacking
execution evidence for positions/accounting are rejected, preserved, and require
explicit investigation. Missing daily adjustment evidence is not backfilled from
the saved daily balance.

## ECONOMIC PNL AND DAILY EVIDENCE

For each position, with sign +1 for LONG and -1 for SHORT:

`realized = sum(sign * (exit - entry) * closed_quantity * point_value)`

The sum includes every partial close and, for CLOSED positions, the remaining
quantity at the terminal PAPER exit. The existing PAPER connector records partial
close fills and a terminal position for a full close; it does not emit a separate
full-close fill. Recovery validates that terminal execution record rather than
manufacturing an exit fill or replaying close_position. Entry quantity minus
partial fills must remain positive and equal the last retained quantity in both
PAPER and portfolio, including their terminal records.

Execution timestamps must be timezone-aware, ordered, and compatible with the
saved trading day. Values use the runtime's existing 10-decimal PnL rounding;
nonfinite or nonpositive execution prices/quantities are rejected. Matching PnL
copies across components are insufficient: all must match execution economics.

The existing explicit `AccountStateManager.record_daily_pnl` API is an account
risk input, not broker execution. It now persists its adjustment amount, recording
time and trading day separately as `daily_pnl_adjustments` in the account snapshot.
Ordinary portfolio synchronization does not create adjustments. Daily reset clears
that day's adjustment list; repeated recovery restores it without replay. A saved
daily value must equal the dated execution sum plus these explicit adjustments.
Changing a balance alone cannot invent supporting adjustment evidence. PENDING
transitions preserve existing same-day adjustments. Existing account risk checks
continue to validate loss capacity, drawdown and structural blocks.

## PENDING RECONCILIATION POLICY

PENDING uses the same semantic validator as COMMITTED, plus operation UUID,
generation/checksum linkage, observation stage and historical immutability checks.
Contradictory candidate evidence remains AMBIGUOUS and blocked. Invalid envelope
or unreconstructable data remains fail-closed; all input evidence is preserved.
Historical PENDING without sufficient operation-bound proof remains AMBIGUOUS.
Only a consistent proven prefix may be restored for PARTIALLY_EXECUTED; unresolved
execution remains blocked. Restoration never replays execution/accounting calls.

## POST-RESTORE VALIDATION

Before marking the store restored or returning success:

1. Capture actual participant state and run semantic validation again.
2. Compare every captured authority against the validated expected snapshot.
3. Ignore only capture time; preserve all operational identities and values.

StateRecoveryService also requires an explicit restored result and verifies the
actual state before publishing success. A partial restoration failure fences the
runtime; input files remain unchanged and retry requires a fresh runtime. PENDING
cannot install its resolved COMMITTED checkpoint until these checks pass. Existing
crash-window and repeated reconciliation protections remain in force.

## PARTIAL CLOSE CONTINUATION

PortfolioManager.close_position now prioritizes lifecycle's explicit cumulative
realized PnL (prior partial realizations plus remaining exit). Without that argument,
it computes the result from previous realized PnL and the remaining quantity/exit.
An open position's cached total_pnl is never authoritative for closing. Terminal
total_pnl is synchronized and unrealized_pnl cleared, preventing the reproduced
journal/history=60 versus portfolio/account=40 discrepancy.

## FAIL-CLOSED CONDITIONS

- Required authorities missing/unshared, PAPER/LIVE mismatch or incomplete schema.
- Missing/duplicate/conflicting order, fill, position or journal identities.
- Quantity, entry/exit price, direction, point value or active SL/TP disagreement.
- CLOSED without terminal PAPER evidence; excessive partial close quantities.
- Stored PnL inconsistent with execution economics or dated daily evidence.
- Any relevant pre-existing destination evidence or incompatible risk block.
- Actual reconstruction differs from expected evidence, including valid-but-different IDs.
- Invalid checkpoint checksum/generation, unresolved PENDING or interrupted writes.

Rejection reports failure, preserves input/destination evidence, fences subsequent
execution and never clears legitimate trading blocks. No LIVE capability, real
broker, secret or read-side endpoint changes are part of this phase.

## Validation

Permanent regression coverage is in `test_recovery_consistency_v2.py`, supplemented
by crash recovery, PENDING reconciliation, execution-state, daily rollover,
portfolio/account, lifecycle, monitor, protection/OCO and journal suites. The first
39 regressions produced 24 failures against the vulnerable implementation before
production changes. Recovery fixtures previously containing fabricated positions
were replaced by actual PAPER execution evidence; their original lifecycle/risk
assertions remain enforced with the new fail-closed contract.

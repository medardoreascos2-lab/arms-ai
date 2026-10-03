# Phase 3 research

The historical dataset registry is append-only and file-backed. Registration
requires an available regular file under an explicit allowed root, valid CSV
or JSONL structure, an exact observed bar count, and an exact SHA-256 digest.
The registry stores immutable metadata for instrument, contract, timeframe,
session template, UTC range, source, standard research window, certification
status, file identity, and registration identity.

The registry never creates, repairs, downloads, or substitutes data. Consumers
must call `require_verified` before use; a missing, invalid, or modified source
fails closed. Certification is descriptive provenance and grants no execution,
production mutation, or administrative authority.

The automated research backtest runner consumes only a currently verified
registry entry. Its identity binds the dataset record and byte hash, strategy
version and source hash, canonical parameter set, exact fee and slippage model,
and optional random seed. Strategies are constructed through an isolated
research factory and return typed decisions. Signals fill on the next bar, one
position at a time, with explicit adverse slippage and per-side fees. Missing,
changed, unordered, malformed, or temporally out-of-range data fails closed.

Results contain deterministic hashes, exact-decimal metrics, a complete trade
list, and an action/block summary. Every run replays the same immutable bars
through a fresh strategy instance a second time and rejects divergent output.
The runner has no broker, PAPER, LIVE, portfolio, or
production state integration and every authority flag remains false.

Strategy experiments bind a stable experiment ID to a parent production
version, an exact candidate parameter set, immutable dataset IDs, and strictly
ordered train, validation, and test windows. Each frozen lifecycle record has a
deterministic hash and links to the prior revision hash. Allowed research states
are `RESEARCH`, `BACKTESTED`, `VALIDATION_FAILED`, `VALIDATION_PASSED`,
`PAPER_CHALLENGER`, `REJECTED`, and `PROMOTION_CANDIDATE`. There is no
`PRODUCTION` research state, and no lifecycle transition grants execution or
production assignment authority.

The walk-forward engine builds deterministic fixed-size rolling windows from a
verified dataset. Each window exposes only its training bars to candidate
selection, freezes the resulting parameter set and training hash, then exposes
only later validation bars to evaluation. Window sizes, step size, and minimum
sample size are explicit. Every run is replayed twice with fresh workflows.
Training and validation failures remain in the result with their window index,
stage, code, and reason; aggregate metrics separately report failed windows and
failed validation outcomes so neither can disappear inside successful totals.

Strict out-of-sample validation is a separate two-step boundary. A candidate can
be frozen only after its experiment reaches `VALIDATION_PASSED`, after the
validation interval ends, and before the OOS interval starts. The freeze pins
the candidate parameters, experiment hash, predeclared gates, OOS interval, and
exact dataset record and byte hashes. Validation later exposes only bars inside
that interval to a fresh evaluator, repeats the evaluation, and fails closed on
changed data, insufficient samples, invalid metrics, evaluator errors, or
non-determinism. Reports include pass/fail, every blocking gate, exact metrics,
drawdown, and trade count. Confidence intervals are explicitly marked as not
implemented rather than estimated without a safe statistical contract.

The stress engine consumes reconciled trade evidence tied to a source run and
result hash. A required seed drives deterministic trade-order permutation,
loss-streak clustering, or return bootstrap paths. Every path can also apply
conservative fee and slippage multipliers, added spread cost, and independent
missed fills. The result retains every simulation and reports exact-decimal PnL
and drawdown distributions, a loss-streak distribution, and a first-passage
risk-of-ruin frequency. Its report names the RNG, model assumptions, seed, and
cost scenario and states that simulated results are neither guarantees nor
forecasts of future performance.

The challenger registry imports one immutable `PRODUCTION_REFERENCE`, then
stores new strategy evidence as append-only `RESEARCH`, `CHALLENGER`, and
`PAPER_CHALLENGER` revisions. Each record binds the strategy source hash,
canonical parameter set, evidence IDs, status, and a hash-chained promotion
history. Research IDs cannot overwrite the production reference, transitions
cannot skip stages or move backward, and neither the registry nor any status
grants PAPER, LIVE, execution, or production-mutation authority.

The promotion gate evaluates a `PAPER_CHALLENGER` against explicit thresholds
for trade count, independent OOS periods, walk-forward consistency, drawdown,
profit factor, expectancy, stress survival, and parameter stability. Evidence
must bind the current immutable challenger revision and its registered evidence
IDs. A passing result can only recommend `PROMOTION_CANDIDATE` for later human
review; it cannot mutate the registry, select production, or authorize any
execution mode.

The weekend research scheduler is an in-process planning boundary with four
explicit modes: `LIVE_MARKET`, `IDLE`, `WEEKEND_RESEARCH`, and
`DEEP_RESEARCH`. A fresh closed-market observation is required before any job
can enter its idempotent research queue. CPU reservations, concurrent jobs,
estimated storage, and absolute maintenance windows are enforced before each
enqueue. Open, stale, idle, and maintenance states create only deferred job
evidence. The scheduler has no OS scheduler, worker, trading, or production
strategy mutation authority.

Automated research reports bind the current immutable registry revision and its
complete evidence set for the production reference and every challenger. Each
side-by-side section includes trades, win rate, expectancy, profit factor,
drawdown, average R, optional MAE/MFE, reconciled session and regime breakdowns,
and gate-reason counts. Reports are hash identified and sort challengers only by
stable strategy ID. They contain no score, rank, automatic winner, production
recommendation, execution authority, or production mutation authority.

Decision-trace analytics classify HOLD, BUY, SELL, blocked signals, near misses,
and candidate entries against one outcome per trace. Outcomes for HOLDs and
rejected entries must carry the explicit
`HYPOTHETICAL_COUNTERFACTUAL_NOT_OBSERVED_EXECUTION` label; accepted entries
must use observed outcomes. The result identifies poor and profitable HOLD
counterfactuals, gates that prevented losses or blocked profitable
opportunities, and descriptive factor correlations. Correlations state that
they are associations rather than causation, and the analytics cannot rewrite
strategy state or authorize execution.

Regime performance analytics aggregate exact outcomes by the five supported
market regimes and by Asia, London, and New York sessions. Labels must already
exist on the source observation as typed values. Missing labels remain counted
as unlabeled evidence, so the engine never infers a regime or session from time,
price, or another proxy. Bucket and overall counts reconcile, inputs and results
are hash identified, and the output carries no strategy rewrite or execution
authority.

Feature attribution compares source-provided baseline predictions with matching
ablation and permutation predictions for BOS, CHOCH, liquidity, FVG, EMA, RSI,
ATR, trend, HTF, L1, and news. It also reports descriptive correlations and a
median-stratified outcome comparison. Every metric is labeled as descriptive or
predictive association, never causation. Reports preserve source hashes, state
the limits of source-provided counterfactual predictions and in-sample evidence,
and cannot rewrite a strategy or authorize execution.

PAPER challenger validation binds one immutable `PAPER_CHALLENGER` identity to
closed simulated sessions, trades, faults, reconciled metrics, and a pinned
`PRODUCTION_REFERENCE` comparison. Trade evidence must be explicitly simulated;
session identities and time windows reconcile before a report is produced. The
hash-identified report has no broker, LIVE, or production mutation authority.

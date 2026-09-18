# Phase 2 Empirical Strategy Certification V15 (MVP-024)

## Purpose

V15 investigates and precisely characterizes MVP-024 (candidate and
validation provenance before release / arbitrary empirical strategy-dataset
certification). It proves how much of `StrategyCertificationPipelineV2` can
be driven by REAL, non-canned engines against an arbitrary dataset, and
documents exactly what remains blocked and why.

LIVE_EXECUTION=NO. PAPER/backtesting only.

## What V15 proves (GREEN)

- Two distinct, arbitrary, non-factory-fixed synthetic CSV datasets are
  certified end-to-end through `StrategyCertificationPipelineV2` using:
  - the REAL `MonteCarloSimulatorV2`/`MonteCarloPipelineV2` (seeded,
    deterministic, no `FakeMonteCarloPipeline`);
  - the REAL `WalkForwardPipelineV2`/`WalkForwardOptimizerV2`/
    `WalkForwardWindowGeneratorV2`/`WalkForwardDatasetSplitterV2` (no
    `FakeWalkForwardPipeline`);
  - the REAL institutional `BacktestEngine` / `PipelineFactory` /
    `BacktestCompositeScoreV2` chain (`build_backtest_engine`) for both the
    top-level backtest score and the per-window training/testing evaluation.
- Empirical trade P&Ls fed to Monte Carlo are the actual `.pnl` values
  produced by running the real strategy pipeline against the arbitrary CSV
  — not the previously hardcoded `[100, -50, 200, 150, -30]` constant.
- Dataset provenance: candle counts and trade P&Ls trace back to the
  specific arbitrary CSV used; two different datasets produce two different,
  independently computed validation scores (not canned/reused numbers).
- Reproducibility: certifying the same dataset twice (fixed seeds) yields
  byte-for-byte identical `StrategyCertificationPipelineResultV2.to_dict()`.
- Negative path: a dataset too small to produce any trade forces the real
  `MonteCarloSimulatorV2` to raise `ValueError("trade_pnls no puede estar
  vacío.")` — certification fails closed, and the registry is not mutated.
- Registry mutation (`StrategyCertificationRegistryServiceV2`) only occurs
  when the real certification status is `CERTIFIED`.

See `backend/tests/test_strategy_certification_empirical_dataset_v15.py`.

## Production changes made (minimal, additive, backward-compatible)

1. `backend/backtesting/strategy_validation_pipeline_v2.py`:
   `StrategyValidationPipelineV2.run()` previously hardcoded its own CSV
   load (`data/backtest/nq_history.csv`), a fixed single `parameter_sets`
   entry, and a canned Monte Carlo `trade_pnls` list — regardless of any
   dataset the caller cared about. Added optional keyword parameters
   `items`, `parameter_sets`, `trade_pnls`, `starting_balance` that default
   to the pre-V15 behavior when omitted (`None`), so every existing caller
   (app.py wiring, V9-V14 tests, other real-e2e tests) is unaffected. This
   is the injection seam required for arbitrary dataset/empirical evidence
   to reach the real Monte Carlo/Walk-Forward engines.
2. `backend/backtesting/strategy_backtest_factory_v2.py`: fixed a
   pre-existing `NameError` — `AccountConfigManagerV2` was only imported
   locally inside `build_lifecycle()`, so `build_strategy_backtest_pipeline()`
   (a sibling function that also references it) always raised `NameError`
   the moment it was invoked outside of a process that had already imported
   that name at module scope. Promoted the import to module level. No
   behavior change for any working caller; this only fixes a call path that
   previously always crashed.

Both changes were validated against the existing certification/backtest
regression surface (761 tests) and the full backend suite (5568 passed / 1
skipped / 0 failed) with zero regressions.

## Exact remaining gap (MVP-024 stays PARTIAL)

While investigating, V15 found that the app.py production wiring for the
walk-forward candidate/testing path
(`BacktestCandidateFactoryV2(pipeline_factory=... build_strategy_backtest_pipeline)`
+ `ParameterEvaluatorAdapterV2(ParameterEvaluator(ParameterBacktestEngineFactoryV2))`)
is **currently broken** the moment it is driven with real candles:
`ParameterizedStrategyRunnerV2.run()` (backend/strategies/
parameterized_strategy_runner_v2.py) calls
`ConfluenceEngineV2.evaluate(trend_context=..., market_structure=...,
ema_alignment=..., momentum=...)`, but the current
`ConfluenceEngineV2.evaluate()` (backend/intelligence/confluence_engine_v2.py)
requires an entirely different keyword contract (`trend_score`,
`structure_score`, `liquidity_score`, `fvg_score`, `ema_alignment_score`,
`market_regime_score`, `probability_score`, `volume_score`, `risk_approved`,
`sizing_approved`, `market_tradable`). Calling the production wiring as-is
raises `TypeError` — it has evidently never been exercised end-to-end with
real candles, only ever through `FakeWalkForwardPipeline`/
`FakeMonteCarloPipeline` doubles in existing tests.

This is a genuine, deeper defect than "fixed application research
factories" — it is a broken call contract between two real production
classes. Fixing it correctly requires reconstructing seven independent 0-1
confluence component scores and three boolean gates from real market/risk
state, which is a non-trivial, architecturally significant change outside
V15's minimal-package scope.

Because of this, V15 exercises `WalkForwardPipelineV2`/`WalkForwardOptimizerV2`
with real, non-canned, dataset-driven training/testing adapters built
directly on the already-working `build_backtest_engine()`/`PipelineFactory`
institutional path, instead of the broken production adapters. This proves
the walk-forward/Monte-Carlo machinery itself works correctly with real
engines and an arbitrary dataset, but it does **not** certify the specific
production wiring in app.py, which remains provably broken.

## Closure rule

MVP-024 may move to CLOSED_CERTIFIED only when:

1. The `ConfluenceEngineV2` / `ParameterizedStrategyRunnerV2` contract defect
   is fixed and verified with a regression test that drives the actual
   app.py-wired `WalkForwardOptimizerV2` (via `BacktestCandidateFactoryV2` +
   `build_strategy_backtest_pipeline` + `ParameterEvaluatorAdapterV2`)
   against real candles without raising;
2. That fixed production wiring is certified against at least one arbitrary
   dataset achieving a real `CERTIFIED` outcome (not only `REJECTED`),
   proving the full gate (score ≥ 90, grade in {A+, A, A-}) is reachable
   empirically, not just theoretically;
3. Full backend regression remains at zero failures.

## V16 minimal package (recommended)

- Fix `ConfluenceEngineV2.evaluate()` call site in
  `ParameterizedStrategyRunnerV2` (or vice versa, whichever is the intended
  canonical contract — requires architecture review, not assumption).
- Add a regression test asserting the production walk-forward wiring
  (`app.state.walk_forward_pipeline_v2` construction pattern) runs against
  real candles without raising.
- Re-run V15's dual-dataset certification against the fixed production
  wiring and confirm at least one dataset reaches `CERTIFIED`.

LIVE_EXECUTION=NO.

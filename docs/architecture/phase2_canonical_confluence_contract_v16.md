# Phase 2 Canonical Confluence Contract V16 (MVP-024)

## Purpose

V16 repairs the stale production caller identified by V15
(`ParameterizedStrategyRunnerV2` calling `ConfluenceEngineV2.evaluate()` with
an obsolete keyword contract) and recertifies the real production
walk-forward wiring used by `backend/api/app.py`.

LIVE_EXECUTION=NO. PAPER/backtesting only.

## Stale contract confirmed

`backend/strategies/parameterized_strategy_runner_v2.py` called:

```python
self.confluence_engine.evaluate(
    trend_context=trend_context,
    market_structure=market_structure,
    ema_alignment=ema_alignment,
    momentum=momentum,
)
```

and then treated the result as an attribute-bearing object
(`confluence.allowed` / `.score` / `.grade` / `.reasons`).

## Canonical contract (unmodified, verified authoritative)

`backend/intelligence/confluence_engine_v2.py::ConfluenceEngineV2.evaluate()`
takes `trend_score, structure_score, liquidity_score, fvg_score,
ema_alignment_score, market_regime_score, probability_score, volume_score,
risk_approved, sizing_approved, market_tradable` (all floats 0-1 except the
three booleans) and returns a **plain dict**: `approved, status, decision,
score, grade, contributions, weights, blocking_reasons`.

This is proven canonical because it is exactly how the real, live
production caller uses it: `backend/services/live_market_analysis_service.py`
`_evaluate_confluence_v2()` calls `evaluate()` with these named score kwargs
and stores/reads the result as `result["confluence_v2"]`, accessed via
`.get(...)` (dict), never via attribute access. `ConfluenceEngineV2` itself
was left untouched — the stale side was the caller.

Existing regression coverage
(`backend/tests/test_confluence_engine_v2.py`) already locks this exact
signature; V16 adds `test_confluence_engine_v2_canonical_signature_is_score_based`
to fail fast if a future change reintroduces drift.

## Production repair (minimal, one canonical authority)

`ParameterizedStrategyRunnerV2.run()` now:

1. Derives each canonical component from real signals already computed in
   the method (not fabricated):
   - `trend_score`: 1.0 when `trend_context.allowed_direction` is
     directional (LONG/SHORT), else 0.50 (mirrors the live caller's own
     neutral-fallback pattern).
   - `structure_score`: `MarketStructureEngineV3` result's own `score`
     field (already 0-100), normalized to 0-1.
   - `ema_alignment_score`: 1.0/0.0 from the already-computed
     `ema_alignment` boolean.
   - `probability_score`: derived from the method's own bullish/bearish
     composite score (0-100), normalized to 0-1.
   - `volume_score`: a new `_estimate_volume_score()` helper — real ratio
     of the latest candle volume to its trailing average when volume data
     is present, else an honest neutral 0.5 (never fabricated).
   - `liquidity_score`, `fvg_score`, `market_regime_score`: this offline
     walk-forward runner has no liquidity/FVG/market-regime detector
     wired in, so these three use an honest, explicitly documented neutral
     0.5 rather than a fabricated high value that would have artificially
     inflated certification odds.
   - `risk_approved`/`sizing_approved`/`market_tradable`: `True`, because
     account risk and position sizing are enforced downstream by the real
     `RiskManagerV2`/`TradeLifecycleServiceV2` in the execution layer for
     this backtest pipeline, not by this signal-generation strategy runner
     (same separation of concerns the live service already uses when a
     sub-system is not wired, e.g. `market_tradable` defaulting to `True`
     when `market_regime_result is None`).
2. Calls `ConfluenceEngineV2.evaluate()` exactly once with these kwargs
   (single canonical decision path, no duplicate confluence invocation).
3. Adapts the returned dict into a small `SimpleNamespace` exposing
   `.allowed` (`approved`), `.score`, `.grade`, `.reasons`
   (`blocking_reasons`) so the rest of the method and
   `TradeQualityEngineV1.evaluate()` (which legitimately expects attribute
   access, per its own dedicated unit tests) are unaffected.

No changes were made to `ConfluenceEngineV2`, `TradeQualityEngineV1`, or any
other canonical authority. `ConfluenceEngineV2` remains the single
confluence authority; `ParameterizedStrategyRunnerV2` is the only repaired
caller (it was also the only production caller of the stale contract).

### Governance manifests updated (not weakened)

Fixing production code changed the AST-derived evidence (source hash,
`calls` list) tracked by three pre-existing architecture-governance
manifests, which now correctly require review of the change:

- `backend/tests/phase1_financial_inventory_v6.json` — updated hash/calls
  for the already-tracked `ParameterizedStrategyRunnerV2.run` entry.
- `backend/tests/phase1_runtime_execution_inventory_v7.json` — same.
- `backend/tests/phase1_risk_authority_inventory_v5.json` — added a new
  entry for `ParameterizedStrategyRunnerV2.run` (the `risk_approved`
  literal it now uses newly matches the AST scanner's risk vocabulary),
  classified `STRATEGY_POLICY`, `account_scoped=false`,
  `execution_scoped=false`, documenting that real risk/sizing enforcement
  happens downstream, not here.

## Recertification evidence

### V16 contract regression
`backend/tests/test_confluence_engine_contract_wiring_v16.py` (5 tests,
GREEN): canonical signature lock, no-crash proof against real (unmocked)
`ConfluenceEngineV2`/`MarketStructureEngineV3`/`TrendContextEngineV2`,
single-invocation proof, deterministic/reproducible decisions, and
structure_score traceability to the real engine output.

### Production wiring recertification
`backend/tests/test_production_walk_forward_confluence_wiring_v16.py`
(2 tests, GREEN) drives the **exact** `backend/api/app.py` composition
(`BacktestCandidateFactoryV2` + `build_strategy_backtest_pipeline` +
`ParameterEvaluatorAdapterV2(ParameterEvaluator(ParameterBacktestEngineFactoryV2))`)
against arbitrary CSV datasets through the real `WalkForwardPipelineV2`/
`WalkForwardOptimizerV2` — no parallel test-only adapter substituted for
this specific wiring (contrast with V15, which had to substitute an
adapter because this wiring used to crash).

`PRODUCTION_CONFLUENCE_WIRING=GREEN`: the wiring now runs to completion on
arbitrary real candle data without raising `TypeError`.

## Genuine remaining gap: no reachable A+/A grade from this offline runner

With `liquidity_score`/`fvg_score`/`market_regime_score` honestly neutral at
0.5 (no detector wired), the maximum achievable `ConfluenceEngineV2` score is
mathematically capped:

- `ConfluenceEngineV2.WEIGHTS` sum to 85 raw points, rescaled to 100
  (`_PRIMARY_WEIGHT_SCALE = 100/85`).
- The three neutral components (liquidity 10, fvg 10, market_regime 15 raw
  = 35 raw points) contribute at most `35 * 0.5 * (100/85) ≈ 20.6` instead
  of `41.2` at full weight.
- Even with every other component (trend, structure, ema_alignment,
  volume = 50 raw points) at a perfect 1.0, the maximum reachable score is
  `20.6 + 50 * (100/85) ≈ 79.4`, always grade `B` or below — never `A`
  (>= 80) or `A+` (>= 90).
- `TradeQualityEngineV1.evaluate()` requires a score >= 85 to approve a
  trade, and its only path to that threshold includes a mandatory +40
  bonus for confluence grade `A+`. Without that bonus the maximum
  achievable trade-quality score is 60 (structure 20 + BOS 15 + no-CHOCH
  15 + HTF-aligned 10), which never reaches approval.

This was verified empirically
(`test_production_confluence_wiring_fails_closed_without_real_trades`) on a
genuine zigzag-structured arbitrary dataset: the repaired wiring runs
end-to-end without error, produces zero authorized trades, and the real,
unmodified `MonteCarloSimulatorV2` correctly raises
`"trade_pnls no puede estar vacío."` — an honest fail-closed outcome, not a
new defect.

Forcing `liquidity_score`/`fvg_score`/`market_regime_score` to 1.0 to make a
trade reachable would fabricate evidence and weaken confluence validation,
which V16 explicitly must not do. Closing this gap requires wiring real
liquidity/FVG/market-regime detectors into the offline walk-forward runner
— a materially larger, separate change (V17), not a minimal contract
repair.

## MVP-024 determination

`PRODUCTION_CONFLUENCE_WIRING=GREEN` (contract fixed and verified), but the
end-to-end empirical certification chain through the *repaired production*
wiring cannot reach a genuine `CERTIFIED` outcome yet — it correctly fails
closed instead. V15's alternate `build_backtest_engine`/`PipelineFactory`
adapters (a different, already-working production strategy path, unrelated
to `ParameterizedStrategyRunnerV2`) remain the only evidence of a real
non-zero-trade arbitrary-dataset certification.

Per the closure rule, MVP-024 **remains PARTIAL**:

```
MVP024_STATUS=PARTIAL
MVP_COMPLETION_PERCENT=95
P0_GAPS=0
P1_GAPS=0
P2_GAPS=1
MVP_READY=False
```

## V17 minimal package (recommended)

- Wire real liquidity/FVG/market-regime detectors into the offline
  walk-forward runner (or intentionally redesign `TradeQualityEngineV1`'s
  approval path for the backtest/offline context, with explicit
  architecture sign-off — not assumed).
- Re-run `test_production_walk_forward_confluence_wiring_v16.py` and
  confirm the "no trades" branch is replaced by a genuine `CERTIFIED`
  outcome on at least one arbitrary dataset.
- Only then consider MVP-024 CLOSED_CERTIFIED.

LIVE_EXECUTION=NO.

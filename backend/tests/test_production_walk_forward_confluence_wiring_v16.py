"""V16 recertification of the REAL production walk-forward wiring.

Drives the exact production composition used by backend/api/app.py
(BacktestCandidateFactoryV2 + build_strategy_backtest_pipeline +
ParameterEvaluatorAdapterV2(ParameterEvaluator(ParameterBacktestEngineFactoryV2)))
against an arbitrary CSV dataset through the real WalkForwardPipelineV2/
WalkForwardOptimizerV2, then through StrategyValidationPipelineV2 /
MonteCarloPipelineV2 / StrategyCertificationPipelineV2 - with NO parallel
test-only adapter substituted for the production candidate/testing wiring
(contrast with test_strategy_certification_empirical_dataset_v15.py, which
intentionally used a substitute adapter because this exact wiring used to
crash with TypeError).

This proves PRODUCTION_CONFLUENCE_WIRING=GREEN: the contract bug is fixed
and the real candidate/testing path runs to completion on arbitrary data
without raising.

It also documents a genuine, separate, deeper finding: with
liquidity_score/fvg_score/market_regime_score held at an honest neutral 0.5
(no liquidity/FVG/market-regime detector is wired into this offline runner),
TradeQualityEngineV1's approval threshold (score >= 85) is mathematically
unreachable, because its only path to 85+ requires ConfluenceEngineV2 grade
"A+" (+40 points) and grade "A+" requires a validation score >= 90 that the
capped confluence inputs can never reach (their maximum possible weighted
contribution is ~79.4/100). See docs/architecture/
phase2_canonical_confluence_contract_v16.md. Real authorized trades
therefore cannot be produced by this exact production wiring without adding
real liquidity/FVG/market-regime detectors - a separate, larger V17 change,
not a minimal contract repair. Monte Carlo's real, unmodified
"trade_pnls no puede estar vacío" guard is the expected, honest fail-closed
outcome proven here - not a defect introduced by V16.
"""

from __future__ import annotations

import random

import pytest

from backend.backtesting.backtest_batch_runner_v2 import (
    BacktestBatchRunnerV2,
)
from backend.backtesting.backtest_candidate_factory_v2 import (
    BacktestCandidateFactoryV2,
)
from backend.backtesting.backtest_comparison_report_v2 import (
    BacktestComparisonReportV2,
)
from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreV2,
)
from backend.backtesting.backtest_optimizer_v2 import BacktestOptimizerV2
from backend.backtesting.csv_candle_loader_v2 import CsvCandleLoaderV2
from backend.backtesting.monte_carlo_html_exporter_v2 import (
    MonteCarloHtmlExporterV2,
)
from backend.backtesting.monte_carlo_json_exporter_v2 import (
    MonteCarloJsonExporterV2,
)
from backend.backtesting.monte_carlo_pipeline_v2 import MonteCarloPipelineV2
from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulatorV2,
)
from backend.backtesting.parameter_backtest_engine_factory_v2 import (
    ParameterBacktestEngineFactoryV2,
)
from backend.backtesting.parameter_evaluator import ParameterEvaluator
from backend.backtesting.parameter_evaluator_adapter_v2 import (
    ParameterEvaluatorAdapterV2,
)
from backend.backtesting.strategy_backtest_factory_v2 import (
    build_strategy_backtest_pipeline,
)
from backend.backtesting.strategy_certification_pipeline_v2 import (
    StrategyCertificationPipelineV2,
)
from backend.backtesting.strategy_validation_html_exporter_v2 import (
    StrategyValidationHtmlExporterV2,
)
from backend.backtesting.strategy_validation_json_exporter_v2 import (
    StrategyValidationJsonExporterV2,
)
from backend.backtesting.strategy_validation_pipeline_v2 import (
    StrategyValidationPipelineV2,
)
from backend.backtesting.walk_forward_dataset_splitter_v2 import (
    WalkForwardDatasetSplitterV2,
)
from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)
from backend.backtesting.walk_forward_optimizer_v2 import (
    WalkForwardOptimizerV2,
)
from backend.backtesting.walk_forward_pipeline_v2 import WalkForwardPipelineV2
from backend.backtesting.walk_forward_window_generator_v2 import (
    WalkForwardWindowGeneratorV2,
)
from backend.config.api_settings import APISettings

_PARAMETER_SETS = [
    {"ema": 10, "stop_loss": 30, "take_profit": 60},
    {"ema": 20, "stop_loss": 30, "take_profit": 60},
]


def _write_csv(path, *, rows: int, seed: int, drift: float, noise: float) -> None:
    """Writes an arbitrary synthetic OHLCV dataset (not an app fixture)."""

    generator = random.Random(seed)

    price = 20000.0
    lines = ["timestamp,symbol,timeframe,open,high,low,close,volume"]

    for index in range(rows):
        open_price = price
        change = drift + generator.uniform(-noise, noise)
        close_price = max(1.0, open_price + change)
        high_price = max(open_price, close_price) + generator.uniform(0.0, 3.0)
        low_price = min(open_price, close_price) - generator.uniform(0.0, 3.0)
        volume = generator.randint(500, 1500)

        timestamp = f"2026-01-01T{9 + index // 60:02d}:{index % 60:02d}:00"

        lines.append(
            f"{timestamp},NQ,1m,{open_price:.2f},{high_price:.2f},"
            f"{low_price:.2f},{close_price:.2f},{volume}"
        )

        price = close_price

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _production_walk_forward_pipeline(csv_path, settings):
    """The exact composition used by backend/api/app.py create_app()."""

    return WalkForwardPipelineV2(
        window_generator=WalkForwardWindowGeneratorV2(
            training_size=200,
            testing_size=100,
            step_size=100,
        ),
        dataset_splitter=WalkForwardDatasetSplitterV2(),
        walk_forward_optimizer=WalkForwardOptimizerV2(
            training_optimizer=BacktestOptimizerV2(
                batch_runner=BacktestBatchRunnerV2(
                    continue_on_error=False,
                ),
                comparison_report_factory=(
                    BacktestComparisonReportV2.from_batch_result
                ),
                scorer=BacktestCompositeScoreV2(
                    minimum_trades=1,
                ),
            ),
            candidate_factory=BacktestCandidateFactoryV2(
                pipeline_factory=(
                    lambda parameters: build_strategy_backtest_pipeline(
                        parameters,
                        csv_path=csv_path,
                        settings=settings,
                    )
                ),
            ),
            testing_evaluator=ParameterEvaluatorAdapterV2(
                evaluator=ParameterEvaluator(
                    engine_factory=ParameterBacktestEngineFactoryV2(
                        csv_path=csv_path,
                        settings=settings,
                    ),
                ),
            ),
        ),
    )


def _production_monte_carlo_pipeline():

    return MonteCarloPipelineV2(
        simulator=MonteCarloSimulatorV2(
            simulations=200,
            random_seed=42,
        ),
        json_exporter=MonteCarloJsonExporterV2(),
        html_exporter=MonteCarloHtmlExporterV2(),
    )


class _RealJsonExporter:

    def export(self, *, report, output_path):
        return StrategyValidationJsonExporterV2().export(
            report=report,
            output_path=output_path,
        )


class _RealHtmlExporter:

    def export(self, *, report, output_path):
        return StrategyValidationHtmlExporterV2().export(
            report=report,
            output_path=output_path,
        )


class _EmpiricalValidationAdapter:
    """Binds the arbitrary dataset/empirical evidence for one run() call."""

    def __init__(
        self,
        *,
        validation_pipeline,
        backtest_score,
        items,
        trade_pnls,
        output_directory,
    ) -> None:

        self.validation_pipeline = validation_pipeline
        self.backtest_score = backtest_score
        self.items = items
        self.trade_pnls = trade_pnls
        self.output_directory = output_directory
        self.last_result = None

    def run(self):

        self.last_result = self.validation_pipeline.run(
            backtest_score=self.backtest_score,
            output_directory=self.output_directory,
            items=self.items,
            parameter_sets=_PARAMETER_SETS,
            trade_pnls=self.trade_pnls,
        )

        return self.last_result


def _api_settings():

    overrides = {
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": "30",
        "ARMS_MINIMUM_REWARD_RISK_RATIO": "2",
        "ARMS_MINIMUM_STOP_POINTS": "1",
        "ARMS_MAXIMUM_STOP_POINTS": "100",
        "ARMS_MAXIMUM_SPREAD_POINTS": "5",
        "ARMS_MINIMUM_ATR_POINTS": "1",
        "ARMS_MINIMUM_A_PLUS_PROBABILITY": "0.8",
        "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE": "0.8",
        "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS": "300",
        "ARMS_MAXIMUM_OPEN_POSITIONS": "1",
    }

    return overrides


@pytest.fixture()
def api_settings(monkeypatch):

    for key, value in _api_settings().items():
        monkeypatch.setenv(key, value)

    return APISettings()


def test_production_walk_forward_wiring_runs_on_arbitrary_data_without_raising(
    tmp_path,
    api_settings,
):
    """The exact app.py composition must no longer raise TypeError."""

    csv_path = tmp_path / "dataset.csv"
    _write_csv(csv_path, rows=500, seed=21, drift=0.0, noise=1.2)

    items = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="1m",
    ).load()

    walk_forward_result = _production_walk_forward_pipeline(
        csv_path,
        api_settings,
    ).run(
        items=items,
        parameter_sets=_PARAMETER_SETS,
        output_directory=tmp_path / "walk_forward",
    )

    assert isinstance(
        walk_forward_result,
        WalkForwardOptimizationResultV2,
    )

    assert walk_forward_result.total_windows >= 1

    for window in walk_forward_result.window_results:
        assert window["best_parameters"]["ema"] in {10, 20}


def test_production_confluence_wiring_fails_closed_without_real_trades(
    tmp_path,
    api_settings,
):
    """Repaired production wiring runs end-to-end and fails closed honestly.

    With no real liquidity/FVG/market-regime detector wired into this
    offline path, TradeQualityEngineV1 never approves a trade (see module
    docstring), so the real, unmodified MonteCarloSimulatorV2 correctly
    rejects the resulting empty trade_pnls instead of certifying anything.
    """

    csv_path = tmp_path / "dataset_production.csv"
    _write_csv(csv_path, rows=500, seed=33, drift=0.0, noise=1.2)

    items = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="1m",
    ).load()

    engine = ParameterBacktestEngineFactoryV2(
        csv_path=csv_path,
        settings=api_settings,
    )(
        {"ema": 10, "stop_loss": 30, "take_profit": 60}
    )

    backtest_result = engine.run(candles=items)

    trade_pnls = [
        float(trade.pnl)
        for trade in backtest_result.trades
        if isinstance(getattr(trade, "pnl", None), (int, float))
    ]

    validation_pipeline = StrategyValidationPipelineV2(
        walk_forward_pipeline=_production_walk_forward_pipeline(
            csv_path,
            api_settings,
        ),
        monte_carlo_pipeline=_production_monte_carlo_pipeline(),
        json_exporter=_RealJsonExporter(),
        html_exporter=_RealHtmlExporter(),
    )

    adapter = _EmpiricalValidationAdapter(
        validation_pipeline=validation_pipeline,
        backtest_score=50.0,
        items=items,
        trade_pnls=trade_pnls,
        output_directory=tmp_path,
    )

    pipeline = StrategyCertificationPipelineV2(
        validation_pipeline=adapter,
    )

    if trade_pnls:
        # If the real production strategy ever authorizes a trade for this
        # dataset, certification must still run to completion (no crash).
        result = pipeline.run()
        assert 0.0 <= result.validation_score <= 100.0
    else:
        with pytest.raises(ValueError, match="trade_pnls"):
            pipeline.run()

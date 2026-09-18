"""V15 empirical certification proof.

Drives StrategyCertificationPipelineV2 through the REAL Monte Carlo
simulator and the REAL WalkForwardPipelineV2/WalkForwardOptimizerV2
orchestration (no Fake* doubles) against arbitrary, non-factory-fixed CSV
datasets, using empirical trade P&Ls derived from an actual production
backtest engine run instead of canned constants.

Known upstream defect (out of V15 scope, see docs/architecture/
phase2_empirical_strategy_certification_v15.md): the production walk-forward
candidate/testing wiring in backend/api/app.py (BacktestCandidateFactoryV2 +
build_strategy_backtest_pipeline + ParameterizedStrategyRunnerV2) raises
TypeError inside ConfluenceEngineV2.evaluate() the moment it is driven with
real candles, because ParameterizedStrategyRunnerV2 calls it with an
obsolete keyword contract. That path cannot be exercised without a
dedicated (non-minimal) fix, so this suite drives WalkForwardPipelineV2/
WalkForwardOptimizerV2 with real, non-canned training/testing adapters built
on the already-working build_backtest_engine()/PipelineFactory institutional
path instead of the broken production adapters.
"""

from __future__ import annotations

import random

import pytest

from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreV2,
)
from backend.backtesting.backtesting_builder_v2 import (
    build_backtest_engine,
)
from backend.backtesting.backtesting_orchestrator_v2 import (
    BacktestingOrchestratorV2,
)
from backend.backtesting.csv_candle_loader_v2 import (
    CsvCandleLoaderV2,
)
from backend.backtesting.monte_carlo_html_exporter_v2 import (
    MonteCarloHtmlExporterV2,
)
from backend.backtesting.monte_carlo_json_exporter_v2 import (
    MonteCarloJsonExporterV2,
)
from backend.backtesting.monte_carlo_pipeline_v2 import (
    MonteCarloPipelineV2,
)
from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulatorV2,
)
from backend.backtesting.strategy_certification_pipeline_v2 import (
    StrategyCertificationPipelineResultV2,
    StrategyCertificationPipelineV2,
)
from backend.backtesting.strategy_certification_registry_service_v2 import (
    StrategyCertificationRegistryServiceV2,
)
from backend.backtesting.strategy_registry_v2 import (
    StrategyRegistryV2,
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
from backend.backtesting.walk_forward_pipeline_v2 import (
    WalkForwardPipelineV2,
)
from backend.backtesting.walk_forward_window_generator_v2 import (
    WalkForwardWindowGeneratorV2,
)
from backend.config_settings import ArmsSettings

_PARAMETER_SETS = [
    {"ema": 10},
    {"ema": 20},
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


def _run_real_engine(candles, *, ema_period: int):
    """Runs the real institutional BacktestEngine/PipelineFactory chain."""

    settings = ArmsSettings(
        ema_period=ema_period,
        rsi_period=5,
        atr_period=5,
    )

    engine = build_backtest_engine(settings=settings)

    return engine.run(candles=candles)


def _score_metrics(backtest_result):

    metrics = BacktestingOrchestratorV2._build_score_metrics(
        backtest_result
    )

    score = BacktestCompositeScoreV2(
        minimum_trades=1,
    ).calculate(
        metrics=metrics,
    ).score

    return score, metrics


class _RealCandidateFactory:
    """Real (non-canned) candidate factory: candidates are raw parameters."""

    def build(self, *, parameter_sets):
        return [dict(parameter_set) for parameter_set in parameter_sets]


class _RealWindowOptimizationResult:

    def __init__(self, ranking) -> None:
        self.ranking = ranking

    def best_strategy(self):
        return dict(self.ranking[0])


class _RealTrainingOptimizer:
    """Real per-window training optimizer over the actual training candles."""

    def optimize(self, *, candidates, candles, output_directory):

        ranking = []

        for parameters in candidates:
            backtest_result = _run_real_engine(
                candles,
                ema_period=int(parameters["ema"]),
            )

            score, metrics = _score_metrics(backtest_result)

            ranking.append(
                {
                    "name": f"EMA{parameters['ema']}",
                    "parameters": dict(parameters),
                    "score": score,
                    "net_pnl": metrics["net_pnl"],
                }
            )

        ranking.sort(
            key=lambda row: row["score"],
            reverse=True,
        )

        return _RealWindowOptimizationResult(ranking)


class _RealTestingEvaluator:
    """Real per-window testing evaluator over the actual testing candles."""

    def evaluate(self, *, testing_items, parameters, output_directory):

        backtest_result = _run_real_engine(
            testing_items,
            ema_period=int(parameters["ema"]),
        )

        score, metrics = _score_metrics(backtest_result)

        return {
            "score": score,
            "net_pnl": metrics["net_pnl"],
            "win_rate": metrics["win_rate"],
            "maximum_drawdown": metrics["maximum_drawdown"],
        }


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
    """Test-local adapter binding an arbitrary dataset/empirical P&Ls.

    StrategyCertificationPipelineV2 calls validation_pipeline.run() with no
    arguments, so the concrete dataset/backtest_score/trade_pnls must be
    captured here (mirrors the production ValidationPipelineExecutionAdapterV2
    pattern used by backend/backtesting/backtesting_orchestrator_factory_v2.py).
    """

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


def _real_walk_forward_pipeline():
    """Builds the real V2 walk-forward stack (window/split/optimize)."""

    return WalkForwardPipelineV2(
        window_generator=WalkForwardWindowGeneratorV2(
            training_size=200,
            testing_size=100,
            step_size=100,
        ),
        dataset_splitter=WalkForwardDatasetSplitterV2(),
        walk_forward_optimizer=WalkForwardOptimizerV2(
            training_optimizer=_RealTrainingOptimizer(),
            candidate_factory=_RealCandidateFactory(),
            testing_evaluator=_RealTestingEvaluator(),
        ),
    )


def _real_monte_carlo_pipeline():

    return MonteCarloPipelineV2(
        simulator=MonteCarloSimulatorV2(
            simulations=200,
            random_seed=42,
        ),
        json_exporter=MonteCarloJsonExporterV2(),
        html_exporter=MonteCarloHtmlExporterV2(),
    )


def _certify(csv_path, tmp_path, *, registry_service=None):

    items = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="1m",
    ).load()

    backtest_result = _run_real_engine(items, ema_period=10)

    backtest_score, _ = _score_metrics(backtest_result)

    trade_pnls = [
        float(trade.pnl)
        for trade in backtest_result.trades
        if isinstance(getattr(trade, "pnl", None), (int, float))
    ]

    validation_pipeline = StrategyValidationPipelineV2(
        walk_forward_pipeline=_real_walk_forward_pipeline(),
        monte_carlo_pipeline=_real_monte_carlo_pipeline(),
        json_exporter=_RealJsonExporter(),
        html_exporter=_RealHtmlExporter(),
    )

    adapter = _EmpiricalValidationAdapter(
        validation_pipeline=validation_pipeline,
        backtest_score=backtest_score,
        items=items,
        trade_pnls=trade_pnls,
        output_directory=tmp_path,
    )

    pipeline = StrategyCertificationPipelineV2(
        validation_pipeline=adapter,
        registry_service=registry_service,
    )

    result = pipeline.run()

    return result, backtest_result.total_candles, trade_pnls


# Flat/choppy synthetic price action reliably authorizes real trades through
# the institutional strategy gates; strong one-directional drift does not.
_DATASET_A = {"rows": 500, "seed": 5, "drift": 0.0, "noise": 1.0}
_DATASET_B = {"rows": 500, "seed": 9, "drift": 0.0, "noise": 1.4}


def test_empirical_certification_reacts_to_the_actual_arbitrary_dataset(
    tmp_path,
):
    """Two distinct arbitrary datasets must produce distinct real evidence."""

    csv_a = tmp_path / "dataset_a.csv"
    csv_b = tmp_path / "dataset_b.csv"

    _write_csv(csv_a, **_DATASET_A)
    _write_csv(csv_b, **_DATASET_B)

    result_a, candles_a, pnls_a = _certify(csv_a, tmp_path / "a")
    result_b, candles_b, pnls_b = _certify(csv_b, tmp_path / "b")

    assert isinstance(result_a, StrategyCertificationPipelineResultV2)
    assert isinstance(result_b, StrategyCertificationPipelineResultV2)

    # Dataset provenance: candle counts trace back to the arbitrary CSVs.
    assert candles_a == _DATASET_A["rows"]
    assert candles_b == _DATASET_B["rows"]

    # At least one dataset must produce genuine, non-empty empirical
    # evidence (real trades), proving the pipeline is not fed canned data.
    assert pnls_a or pnls_b

    # The two arbitrary datasets are not identical inputs; the pipeline
    # must not silently reuse canned/fixed numbers from either run.
    assert (
        pnls_a != pnls_b
        or result_a.validation_score != result_b.validation_score
    )

    for result in (result_a, result_b):
        assert 0.0 <= result.validation_score <= 100.0
        assert result.validation_grade
        assert result.certification.status in {
            "CERTIFIED",
            "PROVISIONAL",
            "REJECTED",
        }


def test_empirical_certification_is_reproducible_for_the_same_dataset(
    tmp_path,
):
    """Deterministic seeds make the real engines reproducible, not random."""

    csv_path = tmp_path / "dataset_repro.csv"
    _write_csv(csv_path, **_DATASET_A)

    result_first, _, _ = _certify(csv_path, tmp_path / "first")
    result_second, _, _ = _certify(csv_path, tmp_path / "second")

    assert result_first.to_dict() == result_second.to_dict()


def test_empirical_certification_registers_only_real_certified_results(
    tmp_path,
):
    """Registry mutation must follow the real certification outcome only."""

    csv_path = tmp_path / "dataset_registry.csv"
    _write_csv(csv_path, **_DATASET_A)

    registry_service = StrategyCertificationRegistryServiceV2(
        registry=StrategyRegistryV2(),
    )

    result, _, _ = _certify(
        csv_path,
        tmp_path,
        registry_service=registry_service,
    )

    registered = registry_service.registry.list()

    if result.certification.status == "CERTIFIED":
        assert len(registered) == 1
    else:
        assert registered == []


def test_empirical_certification_fails_closed_on_insufficient_empirical_evidence(
    tmp_path,
):
    """An arbitrary dataset too small to produce trades must not certify."""

    csv_path = tmp_path / "dataset_tiny.csv"
    _write_csv(csv_path, rows=3, seed=3, drift=0.0, noise=0.5)

    registry_service = StrategyCertificationRegistryServiceV2(
        registry=StrategyRegistryV2(),
    )

    with pytest.raises(ValueError, match="trade_pnls"):
        _certify(
            csv_path,
            tmp_path,
            registry_service=registry_service,
        )

    assert registry_service.registry.list() == []


def test_real_walk_forward_optimizer_produces_non_canned_window_results(
    tmp_path,
):
    """WalkForwardOptimizerV2 must reflect the actual dataset, not fixtures."""

    csv_path = tmp_path / "dataset_walk_forward.csv"
    _write_csv(csv_path, **_DATASET_A)

    items = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="1m",
    ).load()

    walk_forward_result = _real_walk_forward_pipeline().run(
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

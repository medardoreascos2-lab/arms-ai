from pathlib import Path

import pytest

from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreResultV2,
)
from backend.backtesting.backtesting_orchestrator_v2 import (
    BacktestingOrchestratorResultV2,
    BacktestingOrchestratorV2,
)
from backend.models.backtest_result import BacktestResult
from backend.models.backtest_statistics import (
    BacktestStatistics,
)


class FakeBacktestEngine:

    def __init__(self):

        self.candles_received = None
        self.file_path_received = None

    @staticmethod
    def _build_result():

        result = BacktestResult(
            total_candles=100,
            total_signals=30,
            authorized_trades=20,
            blocked_signals=10,
            initial_balance=17000.0,
        )

        result.statistics = BacktestStatistics(
            total_trades=20,
            winning_trades=14,
            losing_trades=6,
            breakeven_trades=0,
            gross_profit=1800.0,
            gross_loss=-600.0,
            net_profit=1200.0,
            win_rate=70.0,
            profit_factor=3.0,
            expectancy=60.0,
            max_drawdown=150.0,
        )

        return result

    def run(
        self,
        *,
        candles,
    ):

        self.candles_received = candles
        return self._build_result()

    def run_from_csv(
        self,
        *,
        file_path,
    ):

        self.file_path_received = Path(
            file_path
        )

        return self._build_result()


class FakeScoreEngine:

    def __init__(self):

        self.metrics_received = None

    def calculate(
        self,
        *,
        metrics,
    ):

        self.metrics_received = dict(
            metrics
        )

        return BacktestCompositeScoreResultV2(
            score=94.5,
            grade="A+",
            strengths=[
                "HIGH_PROFIT_FACTOR",
                "HIGH_WIN_RATE",
            ],
            weaknesses=[],
            components={
                "net_pnl": 25.0,
                "win_rate": 20.0,
                "profit_factor": 20.0,
                "expectancy": 10.0,
                "maximum_drawdown": 19.5,
            },
        )


class FakeCertificationResult:

    def __init__(self):

        self.validation_score = 93.0
        self.validation_grade = "A"
        self.certification = type(
            "Certification",
            (),
            {
                "status": "CERTIFIED",
            },
        )()

    def to_dict(self):

        return {
            "score": {
                "score": self.validation_score,
            },
            "grade": {
                "grade": self.validation_grade,
            },
            "certification": {
                "status": (
                    self.certification.status
                ),
            },
        }


class FakeCertificationPipeline:

    def __init__(
        self,
        *,
        backtest_score,
        output_directory,
    ):

        self.backtest_score = backtest_score
        self.output_directory = (
            Path(output_directory)
        )

    def run(self):

        return FakeCertificationResult()


class FakeCertificationPipelineFactory:

    def __init__(self):

        self.backtest_score_received = None
        self.output_directory_received = None

    def __call__(
        self,
        *,
        backtest_score,
        output_directory,
    ):

        self.backtest_score_received = (
            backtest_score
        )

        self.output_directory_received = (
            Path(output_directory)
        )

        return FakeCertificationPipeline(
            backtest_score=backtest_score,
            output_directory=output_directory,
        )


def build_orchestrator():

    backtest_engine = FakeBacktestEngine()
    score_engine = FakeScoreEngine()

    certification_factory = (
        FakeCertificationPipelineFactory()
    )

    orchestrator = BacktestingOrchestratorV2(
        backtest_engine=backtest_engine,
        score_engine=score_engine,
        certification_pipeline_factory=(
            certification_factory
        ),
    )

    return (
        orchestrator,
        backtest_engine,
        score_engine,
        certification_factory,
    )


def test_runs_complete_orchestration_from_candles(
    tmp_path,
):

    (
        orchestrator,
        backtest_engine,
        score_engine,
        certification_factory,
    ) = build_orchestrator()

    candles = [
        object(),
        object(),
    ]

    result = orchestrator.run(
        candles=candles,
        output_directory=tmp_path,
    )

    assert isinstance(
        result,
        BacktestingOrchestratorResultV2,
    )

    assert isinstance(
        result.backtest_result,
        BacktestResult,
    )

    assert isinstance(
        result.score_result,
        BacktestCompositeScoreResultV2,
    )

    assert backtest_engine.candles_received == candles

    assert score_engine.metrics_received == {
        "net_pnl": 1200.0,
        "win_rate": 0.70,
        "profit_factor": 3.0,
        "expectancy": 60.0,
        "maximum_drawdown": 150.0,
        "total_trades": 20,
    }

    assert (
        certification_factory
        .backtest_score_received
        == 94.5
    )

    assert (
        certification_factory
        .output_directory_received
        == tmp_path
    )

    assert (
        result.certification_result
        .certification.status
        == "CERTIFIED"
    )


def test_runs_complete_orchestration_from_csv(
    tmp_path,
):

    (
        orchestrator,
        backtest_engine,
        _,
        _,
    ) = build_orchestrator()

    csv_path = (
        tmp_path
        / "candles.csv"
    )

    result = orchestrator.run(
        file_path=csv_path,
        output_directory=tmp_path,
    )

    assert (
        backtest_engine.file_path_received
        == csv_path
    )

    assert result.backtest_score == 94.5

    assert (
        result.certification_status
        == "CERTIFIED"
    )


def test_result_to_dict_returns_consolidated_payload(
    tmp_path,
):

    orchestrator, _, _, _ = (
        build_orchestrator()
    )

    result = orchestrator.run(
        candles=[object()],
        output_directory=tmp_path,
    )

    payload = result.to_dict()

    assert payload["backtest"]["total_candles"] == 100

    assert payload["backtest"]["statistics"][
        "net_profit"
    ] == 1200.0

    assert payload["backtest_score"][
        "score"
    ] == 94.5

    assert payload["certification"][
        "certification"
    ]["status"] == "CERTIFIED"


@pytest.mark.parametrize(
    (
        "candles",
        "file_path",
    ),
    [
        (
            None,
            None,
        ),
        (
            [object()],
            "candles.csv",
        ),
    ],
)
def test_requires_exactly_one_backtest_source(
    tmp_path,
    candles,
    file_path,
):

    orchestrator, _, _, _ = (
        build_orchestrator()
    )

    with pytest.raises(
        ValueError,
        match="candles|file_path",
    ):
        orchestrator.run(
            candles=candles,
            file_path=file_path,
            output_directory=tmp_path,
        )


def test_rejects_invalid_dependencies():

    with pytest.raises(
        TypeError,
        match="backtest_engine",
    ):
        BacktestingOrchestratorV2(
            backtest_engine=object(),
            score_engine=FakeScoreEngine(),
            certification_pipeline_factory=(
                FakeCertificationPipelineFactory()
            ),
        )

    with pytest.raises(
        TypeError,
        match="score_engine",
    ):
        BacktestingOrchestratorV2(
            backtest_engine=FakeBacktestEngine(),
            score_engine=object(),
            certification_pipeline_factory=(
                FakeCertificationPipelineFactory()
            ),
        )

    with pytest.raises(
        TypeError,
        match="certification_pipeline_factory",
    ):
        BacktestingOrchestratorV2(
            backtest_engine=FakeBacktestEngine(),
            score_engine=FakeScoreEngine(),
            certification_pipeline_factory=object(),
        )

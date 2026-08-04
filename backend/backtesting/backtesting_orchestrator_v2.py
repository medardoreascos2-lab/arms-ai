from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreResultV2,
)
from backend.backtesting.institutional_backtesting_report_v2 import (
    InstitutionalBacktestingReportV2,
)
from backend.models.backtest_result import (
    BacktestResult,
)


@dataclass(slots=True)
class BacktestingOrchestratorResultV2:
    """
    Resultado consolidado de la ejecución institucional
    de backtesting, scoring y certificación.
    """

    backtest_result: BacktestResult
    score_result: BacktestCompositeScoreResultV2
    certification_result: Any
    institutional_report: InstitutionalBacktestingReportV2

    @property
    def backtest_score(
        self,
    ) -> float:

        return float(
            self.score_result.score
        )

    @property
    def backtest_grade(
        self,
    ) -> str:

        return str(
            self.score_result.grade
        )

    @property
    def certification_status(
        self,
    ) -> str:

        certification = getattr(
            self.certification_result,
            "certification",
            None,
        )

        status = getattr(
            certification,
            "status",
            None,
        )

        if status is None:
            return ""

        return str(status)

    @staticmethod
    def _statistics_to_dict(
        statistics,
    ) -> dict[str, Any]:

        return {
            "total_trades": int(
                getattr(
                    statistics,
                    "total_trades",
                    0,
                )
            ),
            "winning_trades": int(
                getattr(
                    statistics,
                    "winning_trades",
                    0,
                )
            ),
            "losing_trades": int(
                getattr(
                    statistics,
                    "losing_trades",
                    0,
                )
            ),
            "breakeven_trades": int(
                getattr(
                    statistics,
                    "breakeven_trades",
                    0,
                )
            ),
            "gross_profit": float(
                getattr(
                    statistics,
                    "gross_profit",
                    0.0,
                )
            ),
            "gross_loss": float(
                getattr(
                    statistics,
                    "gross_loss",
                    0.0,
                )
            ),
            "net_profit": float(
                getattr(
                    statistics,
                    "net_profit",
                    0.0,
                )
            ),
            "win_rate": float(
                getattr(
                    statistics,
                    "win_rate",
                    0.0,
                )
            ),
            "profit_factor": getattr(
                statistics,
                "profit_factor",
                None,
            ),
            "expectancy": float(
                getattr(
                    statistics,
                    "expectancy",
                    0.0,
                )
            ),
            "max_drawdown": float(
                getattr(
                    statistics,
                    "max_drawdown",
                    0.0,
                )
            ),
        }

    def to_dict(
        self,
    ) -> dict[str, Any]:

        statistics = (
            self.backtest_result.statistics
        )

        certification_to_dict = getattr(
            self.certification_result,
            "to_dict",
            None,
        )

        if callable(certification_to_dict):
            certification_payload = (
                certification_to_dict()
            )
        else:
            certification_payload = {
                "status": (
                    self.certification_status
                ),
            }

        return {
            "backtest": {
                "total_candles": int(
                    self.backtest_result
                    .total_candles
                ),
                "total_signals": int(
                    self.backtest_result
                    .total_signals
                ),
                "authorized_trades": int(
                    self.backtest_result
                    .authorized_trades
                ),
                "blocked_signals": int(
                    self.backtest_result
                    .blocked_signals
                ),
                "initial_balance": float(
                    self.backtest_result
                    .initial_balance
                ),
                "trades_count": len(
                    self.backtest_result.trades
                ),
                "statistics": (
                    self._statistics_to_dict(
                        statistics
                    )
                ),
            },
            "backtest_score": (
                self.score_result.to_dict()
            ),
            "certification": (
                certification_payload
            ),
            "institutional_report": (
                self.institutional_report.to_dict()
            ),
        }


class BacktestingOrchestratorV2:
    """
    Orquesta la ejecución del backtest, convierte
    sus estadísticas en un score compuesto y ejecuta
    el pipeline final de certificación.
    """

    def __init__(
        self,
        *,
        backtest_engine,
        score_engine,
        certification_pipeline_factory,
    ) -> None:

        if not callable(
            getattr(
                backtest_engine,
                "run",
                None,
            )
        ):
            raise TypeError(
                "backtest_engine debe implementar run()."
            )

        if not callable(
            getattr(
                backtest_engine,
                "run_from_csv",
                None,
            )
        ):
            raise TypeError(
                "backtest_engine debe implementar "
                "run_from_csv()."
            )

        if not callable(
            getattr(
                score_engine,
                "calculate",
                None,
            )
        ):
            raise TypeError(
                "score_engine debe implementar "
                "calculate()."
            )

        if not callable(
            certification_pipeline_factory
        ):
            raise TypeError(
                "certification_pipeline_factory "
                "debe ser callable."
            )

        self.backtest_engine = (
            backtest_engine
        )

        self.score_engine = score_engine

        self.certification_pipeline_factory = (
            certification_pipeline_factory
        )

    @staticmethod
    def _normalize_win_rate(
        value,
    ) -> float:

        normalized = float(value)

        if normalized > 1.0:
            normalized = (
                normalized / 100.0
            )

        return max(
            0.0,
            min(
                1.0,
                normalized,
            ),
        )

    @classmethod
    def _build_score_metrics(
        cls,
        backtest_result: BacktestResult,
    ) -> dict[str, Any]:

        statistics = getattr(
            backtest_result,
            "statistics",
            None,
        )

        if statistics is None:
            raise ValueError(
                "backtest_result requiere statistics."
            )

        profit_factor = getattr(
            statistics,
            "profit_factor",
            None,
        )

        if profit_factor is None:
            profit_factor = 0.0

        return {
            "net_pnl": float(
                getattr(
                    statistics,
                    "net_profit",
                    0.0,
                )
            ),
            "win_rate": (
                cls._normalize_win_rate(
                    getattr(
                        statistics,
                        "win_rate",
                        0.0,
                    )
                )
            ),
            "profit_factor": float(
                profit_factor
            ),
            "expectancy": float(
                getattr(
                    statistics,
                    "expectancy",
                    0.0,
                )
            ),
            "maximum_drawdown": abs(
                float(
                    getattr(
                        statistics,
                        "max_drawdown",
                        0.0,
                    )
                )
            ),
            "total_trades": int(
                getattr(
                    statistics,
                    "total_trades",
                    0,
                )
            ),
        }

    def _run_backtest(
        self,
        *,
        candles,
        file_path,
    ) -> BacktestResult:

        has_candles = candles is not None
        has_file_path = file_path is not None

        if has_candles == has_file_path:
            raise ValueError(
                "Debe proporcionar exactamente uno: "
                "candles o file_path."
            )

        if has_candles:
            result = self.backtest_engine.run(
                candles=candles,
            )
        else:
            result = (
                self.backtest_engine
                .run_from_csv(
                    file_path=file_path,
                )
            )

        if not isinstance(
            result,
            BacktestResult,
        ):
            raise TypeError(
                "backtest_engine debe devolver "
                "BacktestResult."
            )

        return result

    def run(
        self,
        *,
        candles=None,
        file_path=None,
        output_directory,
    ) -> BacktestingOrchestratorResultV2:

        output_path = Path(
            output_directory
        )

        output_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        backtest_result = self._run_backtest(
            candles=candles,
            file_path=file_path,
        )

        metrics = self._build_score_metrics(
            backtest_result
        )

        score_result = (
            self.score_engine.calculate(
                metrics=metrics,
            )
        )

        if not isinstance(
            score_result,
            BacktestCompositeScoreResultV2,
        ):
            raise TypeError(
                "score_engine.calculate() debe devolver "
                "BacktestCompositeScoreResultV2."
            )

        certification_pipeline = (
            self.certification_pipeline_factory(
                backtest_score=(
                    score_result.score
                ),
                output_directory=(
                    output_path
                ),
            )
        )

        if not callable(
            getattr(
                certification_pipeline,
                "run",
                None,
            )
        ):
            raise TypeError(
                "certification_pipeline_factory debe "
                "devolver un pipeline con run()."
            )

        certification_result = (
            certification_pipeline.run()
        )

        certification = getattr(
            certification_result,
            "certification",
            None,
        )

        certification_status = getattr(
            certification,
            "status",
            None,
        )

        if certification_status is None:
            raise TypeError(
                "certification_result debe exponer "
                "certification.status."
            )

        institutional_report = (
            InstitutionalBacktestingReportV2(
                backtest_result=backtest_result,
                score_result=score_result,
                certification_status=str(
                    certification_status
                ),
            )
        )

        return BacktestingOrchestratorResultV2(
            backtest_result=backtest_result,
            score_result=score_result,
            certification_result=(
                certification_result
            ),
            institutional_report=(
                institutional_report
            ),
        )

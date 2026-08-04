from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreResultV2,
)
from backend.models.backtest_result import (
    BacktestResult,
)


@dataclass(slots=True)
class InstitutionalBacktestingReportV2:
    """
    Reporte institucional consolidado de backtesting.
    """

    backtest_result: BacktestResult
    score_result: BacktestCompositeScoreResultV2
    certification_status: str

    def __post_init__(self) -> None:

        if not isinstance(
            self.backtest_result,
            BacktestResult,
        ):
            raise TypeError(
                "backtest_result debe ser BacktestResult."
            )

        if not isinstance(
            self.score_result,
            BacktestCompositeScoreResultV2,
        ):
            raise TypeError(
                "score_result debe ser "
                "BacktestCompositeScoreResultV2."
            )

        if not isinstance(
            self.certification_status,
            str,
        ):
            raise TypeError(
                "certification_status debe ser str."
            )

        normalized_status = (
            self.certification_status
            .strip()
            .upper()
        )

        if not normalized_status:
            raise ValueError(
                "certification_status no puede estar vacío."
            )

        self.certification_status = (
            normalized_status
        )

    def _executive_summary(
        self,
    ) -> dict[str, Any]:

        statistics = (
            self.backtest_result.statistics
        )

        return {
            "grade": self.score_result.grade,
            "status": self.certification_status,
            "score": self.score_result.score,
            "total_trades": (
                statistics.total_trades
            ),
            "net_profit": (
                statistics.net_profit
            ),
            "maximum_drawdown": (
                statistics.max_drawdown
            ),
        }

    def _backtest_overview(
        self,
    ) -> dict[str, Any]:

        return {
            "total_candles": (
                self.backtest_result.total_candles
            ),
            "total_signals": (
                self.backtest_result.total_signals
            ),
            "authorized_trades": (
                self.backtest_result.authorized_trades
            ),
            "blocked_signals": (
                self.backtest_result.blocked_signals
            ),
            "initial_balance": (
                self.backtest_result.initial_balance
            ),
            "trades_recorded": len(
                self.backtest_result.trades
            ),
        }

    def _performance(
        self,
    ) -> dict[str, Any]:

        statistics = (
            self.backtest_result.statistics
        )

        return {
            "total_trades": (
                statistics.total_trades
            ),
            "winning_trades": (
                statistics.winning_trades
            ),
            "losing_trades": (
                statistics.losing_trades
            ),
            "breakeven_trades": (
                statistics.breakeven_trades
            ),
            "gross_profit": (
                statistics.gross_profit
            ),
            "gross_loss": (
                statistics.gross_loss
            ),
            "net_profit": (
                statistics.net_profit
            ),
            "win_rate": (
                statistics.win_rate
            ),
            "profit_factor": (
                statistics.profit_factor
            ),
            "expectancy": (
                statistics.expectancy
            ),
            "maximum_drawdown": (
                statistics.max_drawdown
            ),
        }

    def _risk_analysis(
        self,
    ) -> dict[str, Any]:

        statistics = (
            self.backtest_result.statistics
        )

        return {
            "maximum_drawdown": (
                statistics.max_drawdown
            ),
            "drawdown_controlled": (
                statistics.max_drawdown <= 250.0
            ),
            "positive_expectancy": (
                statistics.expectancy > 0.0
            ),
            "profitable": (
                statistics.net_profit > 0.0
            ),
            "sufficient_sample": (
                statistics.total_trades >= 10
            ),
        }

    def _recommendations(
        self,
    ) -> list[str]:

        recommendations: list[str] = []

        if (
            "INSUFFICIENT_TRADES"
            in self.score_result.weaknesses
        ):
            recommendations.append(
                "INCREASE_SAMPLE_SIZE"
            )

        if (
            "HIGH_DRAWDOWN"
            in self.score_result.weaknesses
        ):
            recommendations.append(
                "REDUCE_DRAWDOWN"
            )

        if (
            "LOW_PROFIT_FACTOR"
            in self.score_result.weaknesses
        ):
            recommendations.append(
                "IMPROVE_PROFIT_FACTOR"
            )

        if (
            "NEGATIVE_EXPECTANCY"
            in self.score_result.weaknesses
        ):
            recommendations.append(
                "IMPROVE_EXPECTANCY"
            )

        if (
            self.certification_status
            == "CERTIFIED"
            and not recommendations
        ):
            recommendations.append(
                "READY_FOR_CONTROLLED_DEPLOYMENT"
            )

        if not recommendations:
            recommendations.append(
                "CONTINUE_VALIDATION"
            )

        return recommendations

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "executive_summary": (
                self._executive_summary()
            ),
            "backtest_overview": (
                self._backtest_overview()
            ),
            "performance": (
                self._performance()
            ),
            "score": (
                self.score_result.to_dict()
            ),
            "strengths": list(
                self.score_result.strengths
            ),
            "weaknesses": list(
                self.score_result.weaknesses
            ),
            "risk_analysis": (
                self._risk_analysis()
            ),
            "recommendations": (
                self._recommendations()
            ),
        }

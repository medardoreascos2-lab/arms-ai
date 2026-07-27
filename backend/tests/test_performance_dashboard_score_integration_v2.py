import pytest

from backend.dashboard.performance_dashboard_engine_v2 import (
    PerformanceDashboardEngineV2,
)
from backend.performance.performance_score_engine_v2 import (
    PerformanceScoreEngineV2,
)


class FakeAccountStateManager:

    def get_state(self):
        return {
            "balance": 17100.0,
            "equity": 17150.0,
            "daily_pnl": 250.0,
            "drawdown": 500.0,
            "maximum_total_drawdown": 4500.0,
            "open_risk": 200.0,
            "open_positions": 1,
            "closed_positions": 3,
            "trading_blocked": False,
            "blocking_reasons": [],
        }


class FakePortfolioManager:

    def get_summary(self):
        return {
            "starting_balance": 17000.0,
            "open_positions": 1,
            "closed_positions": 3,
            "total_realized_pnl": 100.0,
            "total_unrealized_pnl": 50.0,
            "total_pnl": 150.0,
            "account_equity": 17150.0,
        }


class FakeTradeJournal:

    def get_summary(self):
        return {
            "open_trades": 1,
            "closed_trades": 3,
            "winning_trades": 2,
            "losing_trades": 1,
            "total_realized_pnl": 100.0,
            "win_rate": 66.6666666667,
            "analytics": {
                "total_trades": 3,
                "winning_trades": 2,
                "losing_trades": 1,
                "breakeven_trades": 0,
                "gross_profit": 200.0,
                "gross_loss": 100.0,
                "net_profit": 100.0,
                "average_win": 100.0,
                "average_loss": 100.0,
                "largest_win": 125.0,
                "largest_loss": -100.0,
                "win_rate": 66.6666666667,
                "profit_factor": 2.0,
                "expectancy": 40.0,
                "average_duration_seconds": 420.0,
            },
            "breakdown": {
                "by_symbol": {},
                "by_direction": {},
                "by_session": {},
                "by_strategy": {},
                "by_timeframe": {},
                "by_exit_reason": {},
            },
        }


def build_engine(
    *,
    performance_score_engine=None,
):
    return PerformanceDashboardEngineV2(
        account_state_manager_v2=(
            FakeAccountStateManager()
        ),
        portfolio_manager_v2=(
            FakePortfolioManager()
        ),
        trade_journal_v2=(
            FakeTradeJournal()
        ),
        performance_score_engine_v2=(
            performance_score_engine
        ),
    )


def test_accepts_none_score_engine():
    engine = build_engine(
        performance_score_engine=None,
    )

    assert (
        engine.performance_score_engine_v2
        is None
    )


def test_accepts_valid_score_engine():
    score_engine = (
        PerformanceScoreEngineV2()
    )

    engine = build_engine(
        performance_score_engine=(
            score_engine
        ),
    )

    assert (
        engine.performance_score_engine_v2
        is score_engine
    )


def test_rejects_invalid_score_engine():
    with pytest.raises(
        TypeError,
        match="performance_score_engine_v2",
    ):
        build_engine(
            performance_score_engine=object(),
        )


def test_build_returns_none_score_without_engine():
    engine = build_engine(
        performance_score_engine=None,
    )

    result = engine.build()

    assert (
        result["performance_score"]
        is None
    )


def test_build_includes_performance_score():
    score_engine = (
        PerformanceScoreEngineV2()
    )

    engine = build_engine(
        performance_score_engine=(
            score_engine
        ),
    )

    result = engine.build()

    score = result[
        "performance_score"
    ]

    assert isinstance(
        score["score"],
        int,
    )

    assert score["score"] > 0

    assert score["grade"] in {
        "A+",
        "A",
        "B+",
        "B",
        "C",
    }

    assert (
        "recommendation"
        in score
    )

    assert (
        "score_breakdown"
        in score
    )


def test_blocked_dashboard_returns_blocked_score():
    class BlockedAccountStateManager:

        def get_state(self):
            return {
                "balance": 14000.0,
                "equity": 12500.0,
                "daily_pnl": -3000.0,
                "drawdown": 4500.0,
                "maximum_total_drawdown": 4500.0,
                "open_risk": 0.0,
                "open_positions": 0,
                "closed_positions": 10,
                "trading_blocked": True,
                "blocking_reasons": [
                    "daily_loss_limit_reached",
                ],
            }

    engine = (
        PerformanceDashboardEngineV2(
            account_state_manager_v2=(
                BlockedAccountStateManager()
            ),
            portfolio_manager_v2=None,
            trade_journal_v2=None,
            performance_score_engine_v2=(
                PerformanceScoreEngineV2()
            ),
        )
    )

    result = engine.build()

    score = result[
        "performance_score"
    ]

    assert score["score"] == 0
    assert score["grade"] == "F"
    assert score["status"] == "BLOCKED"
    assert (
        score["recommendation"]
        == "STOP_TRADING"
    )

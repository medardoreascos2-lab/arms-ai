import pytest

from backend.dashboard.performance_dashboard_engine_v2 import (
    PerformanceDashboardEngineV2,
)


class FakeAccountStateManager:

    def get_state(self):
        return {
            "balance": 17100.0,
            "equity": 17150.0,
            "daily_pnl": 100.0,
            "drawdown": 50.0,
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
                "expectancy": 33.3333333333,
                "average_duration_seconds": 420.0,
            },
            "breakdown": {
                "by_symbol": {
                    "NQ": {
                        "total_trades": 3,
                        "winning_trades": 2,
                        "losing_trades": 1,
                        "breakeven_trades": 0,
                        "net_profit": 100.0,
                        "win_rate": 66.6666666667,
                    }
                },
                "by_direction": {},
                "by_session": {},
                "by_strategy": {},
                "by_timeframe": {},
                "by_exit_reason": {},
            },
        }


def build_engine(
    *,
    account_state_manager=None,
    portfolio_manager=None,
    trade_journal=None,
):
    return PerformanceDashboardEngineV2(
        account_state_manager_v2=(
            account_state_manager
        ),
        portfolio_manager_v2=(
            portfolio_manager
        ),
        trade_journal_v2=(
            trade_journal
        ),
    )


def test_accepts_none_dependencies():
    engine = build_engine()

    assert (
        engine.account_state_manager_v2
        is None
    )

    assert (
        engine.portfolio_manager_v2
        is None
    )

    assert (
        engine.trade_journal_v2
        is None
    )


def test_builds_empty_dashboard():
    engine = build_engine()

    result = engine.build()

    assert result["account_state"] is None
    assert result["portfolio_summary"] is None
    assert result["trade_journal_summary"] is None
    assert result["analytics"] is None
    assert result["breakdown"] is None
    assert result["dashboard_status"] == "EMPTY"


def test_builds_complete_dashboard():
    engine = build_engine(
        account_state_manager=(
            FakeAccountStateManager()
        ),
        portfolio_manager=(
            FakePortfolioManager()
        ),
        trade_journal=(
            FakeTradeJournal()
        ),
    )

    result = engine.build()

    assert result["dashboard_status"] == "READY"

    assert (
        result["account_state"][
            "equity"
        ]
        == 17150.0
    )

    assert (
        result["portfolio_summary"][
            "total_pnl"
        ]
        == 150.0
    )

    assert (
        result["trade_journal_summary"][
            "closed_trades"
        ]
        == 3
    )

    assert (
        result["analytics"][
            "profit_factor"
        ]
        == 2.0
    )

    assert (
        result["breakdown"][
            "by_symbol"
        ]["NQ"]["net_profit"]
        == 100.0
    )


def test_builds_account_overview():
    engine = build_engine(
        account_state_manager=(
            FakeAccountStateManager()
        ),
        portfolio_manager=(
            FakePortfolioManager()
        ),
        trade_journal=(
            FakeTradeJournal()
        ),
    )

    result = engine.build()

    overview = result[
        "account_overview"
    ]

    assert overview["balance"] == 17100.0
    assert overview["equity"] == 17150.0
    assert overview["daily_pnl"] == 100.0
    assert overview["drawdown"] == 50.0
    assert overview["open_risk"] == 200.0


def test_builds_performance_overview():
    engine = build_engine(
        account_state_manager=(
            FakeAccountStateManager()
        ),
        portfolio_manager=(
            FakePortfolioManager()
        ),
        trade_journal=(
            FakeTradeJournal()
        ),
    )

    result = engine.build()

    performance = result[
        "performance_overview"
    ]

    assert performance["total_trades"] == 3
    assert performance["win_rate"] == pytest.approx(
        66.6666666667
    )
    assert performance["profit_factor"] == 2.0
    assert performance["expectancy"] == pytest.approx(
        33.3333333333
    )
    assert performance["net_profit"] == 100.0


def test_builds_risk_status():
    engine = build_engine(
        account_state_manager=(
            FakeAccountStateManager()
        ),
    )

    result = engine.build()

    risk_status = result[
        "risk_status"
    ]

    assert risk_status["trading_blocked"] is False
    assert risk_status["blocking_reasons"] == []
    assert risk_status["drawdown"] == 50.0
    assert risk_status["open_risk"] == 200.0


def test_detects_blocked_dashboard():
    class BlockedAccountStateManager:

        def get_state(self):
            return {
                "balance": 14000.0,
                "equity": 12500.0,
                "daily_pnl": -3000.0,
                "drawdown": 4500.0,
                "open_risk": 0.0,
                "open_positions": 0,
                "closed_positions": 10,
                "trading_blocked": True,
                "blocking_reasons": [
                    "daily_loss_limit_reached",
                    "maximum_total_drawdown_reached",
                ],
            }

    engine = build_engine(
        account_state_manager=(
            BlockedAccountStateManager()
        ),
    )

    result = engine.build()

    assert result["dashboard_status"] == "BLOCKED"

    assert (
        result["risk_status"][
            "trading_blocked"
        ]
        is True
    )


@pytest.mark.parametrize(
    (
        "argument",
        "value",
    ),
    [
        (
            "account_state_manager",
            object(),
        ),
        (
            "portfolio_manager",
            object(),
        ),
        (
            "trade_journal",
            object(),
        ),
    ],
)
def test_rejects_invalid_dependencies(
    argument,
    value,
):
    kwargs = {
        "account_state_manager": None,
        "portfolio_manager": None,
        "trade_journal": None,
    }

    kwargs[argument] = value

    with pytest.raises(
        TypeError,
        match=argument,
    ):
        build_engine(
            **kwargs,
        )


def test_uses_trade_journal_analytics_as_fallback():

    engine = build_engine(
        account_state_manager=(
            FakeAccountStateManager()
        ),
        portfolio_manager=(
            FakePortfolioManager()
        ),
        trade_journal=(
            FakeTradeJournal()
        ),
    )

    result = engine.build()

    assert result["analytics"] is not None

    assert (
        result["analytics"]["win_rate"]
        == pytest.approx(
            66.6666666667
        )
    )

    assert (
        result["performance_overview"][
            "win_rate"
        ]
        == pytest.approx(
            66.6666666667
        )
    )

    assert (
        result["performance_overview"][
            "net_profit"
        ]
        == 100.0
    )


def test_new_analytics_ratio_is_exposed_as_percent():

    class FakeAnalytics:

        def analyze(
            self,
            *,
            trades,
            starting_balance,
        ):
            return {
                "total_trades": 2,
                "wins": 1,
                "losses": 1,
                "break_even": 0,
                "win_rate": 0.5,
                "profit_factor": 2.0,
                "expectancy": 25.0,
                "net_pnl": 50.0,
            }

    class FakeJournalWithTrades(
        FakeTradeJournal
    ):

        def get_trades(self):
            return []

    engine = PerformanceDashboardEngineV2(
        account_state_manager_v2=(
            FakeAccountStateManager()
        ),
        portfolio_manager_v2=(
            FakePortfolioManager()
        ),
        trade_journal_v2=(
            FakeJournalWithTrades()
        ),
        performance_analytics_v2=(
            FakeAnalytics()
        ),
    )

    result = engine.build()

    assert (
        result["analytics"]["win_rate"]
        == 0.5
    )

    assert (
        result["performance_overview"][
            "win_rate"
        ]
        == 50.0
    )

    assert (
        result["performance_overview"][
            "net_profit"
        ]
        == 50.0
    )

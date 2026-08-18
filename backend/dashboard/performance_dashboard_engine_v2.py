from __future__ import annotations

from backend.performance.performance_score_engine_v2 import (
    PerformanceScoreEngineV2,
)



class PerformanceDashboardEngineV2:

    def __init__(
        self,
        *,
        account_state_manager_v2=None,
        portfolio_manager_v2=None,
        trade_journal_v2=None,
        performance_score_engine_v2=None,
        performance_analytics_v2=None,
    ) -> None:

        if (
            account_state_manager_v2
            is not None
            and not hasattr(
                account_state_manager_v2,
                "get_state",
            )
        ):
            raise TypeError(
                "account_state_manager debe implementar get_state()."
            )

        if (
            portfolio_manager_v2
            is not None
            and not hasattr(
                portfolio_manager_v2,
                "get_summary",
            )
        ):
            raise TypeError(
                "portfolio_manager debe implementar get_summary()."
            )

        if (
            trade_journal_v2
            is not None
            and not hasattr(
                trade_journal_v2,
                "get_summary",
            )
        ):
            raise TypeError(
                "trade_journal debe implementar get_summary()."
            )

        self.account_state_manager_v2 = (
            account_state_manager_v2
        )

        self.portfolio_manager_v2 = (
            portfolio_manager_v2
        )

        self.trade_journal_v2 = (
            trade_journal_v2
        )

        if (
            performance_score_engine_v2
            is not None
            and not isinstance(
                performance_score_engine_v2,
                PerformanceScoreEngineV2,
            )
        ):
            raise TypeError(
                "performance_score_engine_v2 debe ser "
                "PerformanceScoreEngineV2."
            )

        self.performance_score_engine_v2 = (
            performance_score_engine_v2
        )


        self.performance_analytics_v2 = (
            performance_analytics_v2
        )

    def build(
        self,
    ) -> dict[str, object]:

        account_state = (
            self.account_state_manager_v2.get_state()
            if self.account_state_manager_v2
            is not None
            else None
        )

        portfolio_summary = (
            self.portfolio_manager_v2.get_summary()
            if self.portfolio_manager_v2
            is not None
            else None
        )

        trade_journal_summary = (
            self.trade_journal_v2.get_summary()
            if self.trade_journal_v2
            is not None
            else None
        )

        analytics = (
            trade_journal_summary.get(
                "analytics"
            )
            if trade_journal_summary
            else None
        )


        if (
            self.performance_analytics_v2
            is not None
            and self.trade_journal_v2
            is not None
        ):

            analytics = (
                self.performance_analytics_v2.analyze(
                    trades=[
                        trade
                        if isinstance(
                            trade,
                            dict,
                        )
                        else {
                            "trade_id": trade.trade_id,
                            "symbol": trade.symbol,
                            "direction": trade.direction,
                            "entry_price": trade.entry,
                            "exit_price": trade.exit_price,
                            "quantity": trade.contracts,
                            "realized_pnl": trade.pnl,
                            "status": trade.status,
                            "result": trade.result,
                            "exit_reason": trade.exit_reason,
                        }
                        for trade
                        in self.trade_journal_v2.get_trades()
                    ],
                    starting_balance=17000.0,
                )
            )

        breakdown = (
            trade_journal_summary.get(
                "breakdown"
            )
            if trade_journal_summary
            else None
        )

        if account_state is None:
            dashboard_status = "EMPTY"
        elif account_state.get(
            "trading_blocked",
            False,
        ):
            dashboard_status = "BLOCKED"
        else:
            dashboard_status = "READY"

        account_overview = (
            {
                "balance":
                    account_state["balance"],
                "equity":
                    account_state["equity"],
                "daily_pnl":
                    account_state["daily_pnl"],
                "drawdown":
                    account_state["drawdown"],
                "open_risk":
                    account_state["open_risk"],
            }
            if account_state
            else None
        )

        performance_overview = (
            {
                "total_trades":
                    analytics["total_trades"],
                "win_rate":
                    (
                        analytics["win_rate"] * 100.0
                        if "net_pnl" in analytics
                        else analytics["win_rate"]
                    ),
                "profit_factor":
                    analytics["profit_factor"],
                "expectancy":
                    analytics["expectancy"],
                "net_profit":
                    analytics.get(
                        "net_pnl",
                        analytics.get(
                            "net_profit",
                            0.0,
                        ),
                    ),
            }
            if analytics
            else None
        )

        risk_status = (
            {
                "trading_blocked":
                    account_state["trading_blocked"],
                "blocking_reasons":
                    account_state["blocking_reasons"],
                "drawdown":
                    account_state["drawdown"],
                "open_risk":
                    account_state["open_risk"],
            }
            if account_state
            else None
        )


        performance_score = (
            self.performance_score_engine_v2.calculate(
                dashboard={
                    "dashboard_status": dashboard_status,
                    "account_state": account_state,
                    "analytics": analytics,
                },
            )
            if self.performance_score_engine_v2
            is not None
            else None
        )

        return {
            "account_state":
                account_state,
            "portfolio_summary":
                portfolio_summary,
            "trade_journal_summary":
                trade_journal_summary,
            "analytics":
                analytics,
            "breakdown":
                breakdown,
            "account_overview":
                account_overview,
            "performance_overview":
                performance_overview,
            "risk_status":
                risk_status,
            "performance_score":
                performance_score,
            "dashboard_status":
                dashboard_status,
        }

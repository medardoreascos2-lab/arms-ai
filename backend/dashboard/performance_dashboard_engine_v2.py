from __future__ import annotations


class PerformanceDashboardEngineV2:

    def __init__(
        self,
        *,
        account_state_manager_v2=None,
        portfolio_manager_v2=None,
        trade_journal_v2=None,
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
                    analytics["win_rate"],
                "profit_factor":
                    analytics["profit_factor"],
                "expectancy":
                    analytics["expectancy"],
                "net_profit":
                    analytics["net_profit"],
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
            "dashboard_status":
                dashboard_status,
        }

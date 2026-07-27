from __future__ import annotations


class PerformanceScoreEngineV2:

    def calculate(
        self,
        *,
        dashboard: dict[str, object],
    ) -> dict[str, object]:

        if not isinstance(
            dashboard,
            dict,
        ):
            raise TypeError(
                "dashboard debe ser un dict."
            )

        status = dashboard.get(
            "dashboard_status"
        )

        if status == "EMPTY":
            return {
                "score": 0,
                "grade": "N/A",
                "status": "NO_DATA",
                "recommendation": "WAIT_FOR_DATA",
                "penalties": [],
                "score_breakdown": {},
            }

        account = (
            dashboard.get(
                "account_state"
            )
            or {}
        )

        analytics = (
            dashboard.get(
                "analytics"
            )
            or {}
        )

        if account.get(
            "trading_blocked",
            False,
        ):
            return {
                "score": 0,
                "grade": "F",
                "status": "BLOCKED",
                "recommendation": "STOP_TRADING",
                "penalties": [
                    "account_blocked",
                ],
                "score_breakdown": {},
            }

        win_rate = float(
            analytics.get(
                "win_rate",
                0.0,
            )
        )

        raw_profit_factor = analytics.get(
            "profit_factor"
        )

        if raw_profit_factor is None:
            profit_factor = 0.0
        else:
            profit_factor = float(
                raw_profit_factor
            )

        expectancy = float(
            analytics.get(
                "expectancy",
                0.0,
            )
        )

        daily_pnl = float(
            account.get(
                "daily_pnl",
                0.0,
            )
        )

        drawdown = float(
            account.get(
                "drawdown",
                0.0,
            )
        )

        max_drawdown = max(
            1.0,
            float(
                account.get(
                    "maximum_total_drawdown",
                    4500.0,
                )
            ),
        )

        penalties = []

        win_rate_score = min(
            30.0,
            win_rate / 70.0 * 30.0,
        )

        profit_factor_score = min(
            30.0,
            profit_factor / 2.0 * 30.0,
        )

        expectancy_score = min(
            20.0,
            expectancy / 50.0 * 20.0,
        )

        drawdown_ratio = (
            drawdown
            / max_drawdown
        )

        drawdown_score = max(
            0.0,
            15.0
            * (1 - drawdown_ratio),
        )

        if drawdown_ratio >= 0.80:
            penalties.append(
                "high_drawdown"
            )

            score_penalty = 15.0
        else:
            score_penalty = 0.0

        daily_score = min(
            5.0,
            max(
                0.0,
                daily_pnl / 500.0 * 5.0,
            ),
        )

        score = round(
            win_rate_score
            + profit_factor_score
            + expectancy_score
            + drawdown_score
            + daily_score
            - score_penalty
        )

        if score >= 90:
            grade = "A+"
            state = "EXCELLENT"
            recommendation = (
                "CONTINUE_TRADING"
            )
        elif score >= 80:
            grade = "A"
            state = "GOOD"
            recommendation = (
                "CONTINUE_TRADING"
            )
        elif score >= 75:
            grade = "B+"
            state = "GOOD"
            recommendation = (
                "CONTINUE_TRADING"
            )
        elif score >= 60:
            grade = "B"
            state = "AVERAGE"
            recommendation = (
                "REDUCE_RISK"
            )
        else:
            grade = "C"
            state = "POOR"
            recommendation = (
                "STOP_AND_REVIEW"
            )

        return {
            "score": score,
            "grade": grade,
            "status": state,
            "recommendation": recommendation,
            "penalties": penalties,
            "score_breakdown": {
                "win_rate_score": win_rate_score,
                "profit_factor_score": profit_factor_score,
                "expectancy_score": expectancy_score,
                "drawdown_score": drawdown_score,
                "daily_pnl_score": daily_score,
            },
        }

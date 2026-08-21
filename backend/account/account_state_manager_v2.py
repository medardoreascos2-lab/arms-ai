from __future__ import annotations

from copy import deepcopy


class AccountStateManagerV2:

    def __init__(
        self,
        *,
        starting_balance: float,
        maximum_daily_loss: float | None,
        maximum_total_drawdown: float,
        profit_target: float | None = None,
        account_stage: str | None = None,
    ) -> None:

        starting_balance = float(
            starting_balance
        )

        maximum_daily_loss = (
            None
            if maximum_daily_loss is None
            else float(maximum_daily_loss)
        )

        maximum_total_drawdown = float(
            maximum_total_drawdown
        )

        profit_target = (
            None
            if profit_target is None
            else float(profit_target)
        )

        account_stage = (
            None
            if account_stage is None
            else str(account_stage)
            .strip()
            .upper()
        )

        if starting_balance <= 0:
            raise ValueError(
                "starting_balance debe ser mayor que cero."
            )

        if (
            maximum_daily_loss is not None
            and maximum_daily_loss <= 0
        ):
            raise ValueError(
                "maximum_daily_loss debe ser mayor que cero "
                "cuando está definido."
            )

        if maximum_total_drawdown <= 0:
            raise ValueError(
                "maximum_total_drawdown debe ser mayor que cero."
            )

        if (
            profit_target is not None
            and profit_target <= 0
        ):
            raise ValueError(
                "profit_target debe ser mayor que cero "
                "cuando está definido."
            )

        self._state = {
            "starting_balance": starting_balance,
            "account_stage": account_stage,
            "evaluation_status": (
                "IN_PROGRESS"
                if account_stage
                == "TRADING_COMBINE"
                else "NOT_APPLICABLE"
            ),
            "profit_target": profit_target,
            "profit_achieved": 0.0,
            "profit_remaining": profit_target,
            "profit_progress_percent": (
                0.0
                if profit_target is not None
                else None
            ),
            "target_reached": False,
            "balance": starting_balance,
            "equity": starting_balance,
            "peak_equity": starting_balance,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "total_pnl": 0.0,
            "daily_pnl": 0.0,
            "daily_loss_used": 0.0,
            "remaining_daily_loss_capacity":
                maximum_daily_loss,
            "drawdown": 0.0,
            "remaining_drawdown_capacity":
                maximum_total_drawdown,
            "open_positions": 0,
            "closed_positions": 0,
            "open_risk": 0.0,
            "trading_blocked": False,
            "blocking_reasons": [],
        }

        self.maximum_daily_loss = (
            maximum_daily_loss
        )

        self.maximum_total_drawdown = (
            maximum_total_drawdown
        )

        self.profit_target = profit_target
        self.account_stage = account_stage

    def get_state(
        self,
    ) -> dict[str, object]:
        return deepcopy(
            self._state
        )

    def update_from_portfolio(
        self,
        *,
        portfolio_summary: dict[str, object],
    ) -> dict[str, object]:
        if not isinstance(
            portfolio_summary,
            dict,
        ):
            raise TypeError(
                "portfolio_summary debe ser un dict."
            )

        open_positions = int(
            portfolio_summary.get(
                "open_positions",
                0,
            )
        )

        closed_positions = int(
            portfolio_summary.get(
                "closed_positions",
                0,
            )
        )

        realized_pnl = float(
            portfolio_summary.get(
                "total_realized_pnl",
                0.0,
            )
        )

        unrealized_pnl = float(
            portfolio_summary.get(
                "total_unrealized_pnl",
                0.0,
            )
        )

        total_pnl = float(
            portfolio_summary.get(
                "total_pnl",
                realized_pnl
                + unrealized_pnl,
            )
        )

        account_equity = float(
            portfolio_summary.get(
                "account_equity",
                0.0,
            )
        )

        if open_positions < 0:
            raise ValueError(
                "open_positions no puede ser negativo."
            )

        if closed_positions < 0:
            raise ValueError(
                "closed_positions no puede ser negativo."
            )

        if account_equity <= 0:
            raise ValueError(
                "account_equity debe ser mayor que cero."
            )

        balance = round(
            float(
                self._state[
                    "starting_balance"
                ]
            )
            + realized_pnl,
            10,
        )

        previous_peak_equity = float(
            self._state[
                "peak_equity"
            ]
        )

        peak_equity = max(
            previous_peak_equity,
            account_equity,
        )

        drawdown = round(
            max(
                0.0,
                peak_equity
                - account_equity,
            ),
            10,
        )

        remaining_drawdown_capacity = round(
            max(
                0.0,
                self.maximum_total_drawdown
                - drawdown,
            ),
            10,
        )

        self._state[
            "balance"
        ] = balance

        self._state[
            "equity"
        ] = account_equity

        self._state[
            "peak_equity"
        ] = peak_equity

        self._state[
            "realized_pnl"
        ] = realized_pnl

        profit_target = (
            self.profit_target
        )

        profit_achieved = round(
            realized_pnl,
            10,
        )

        if profit_target is None:
            profit_remaining = None
            profit_progress_percent = None
            target_reached = False
        else:
            profit_remaining = round(
                max(
                    0.0,
                    profit_target
                    - profit_achieved,
                ),
                10,
            )

            profit_progress_percent = round(
                max(
                    0.0,
                    min(
                        100.0,
                        (
                            profit_achieved
                            / profit_target
                        )
                        * 100.0,
                    ),
                ),
                10,
            )

            target_reached = (
                profit_achieved
                >= profit_target
            )

        self._state[
            "profit_achieved"
        ] = profit_achieved

        self._state[
            "profit_remaining"
        ] = profit_remaining

        self._state[
            "profit_progress_percent"
        ] = profit_progress_percent

        self._state[
            "target_reached"
        ] = target_reached

        if (
            self.account_stage
            == "TRADING_COMBINE"
        ):
            evaluation_status = (
                "FAILED"
                if drawdown
                >= self.maximum_total_drawdown
                else (
                    "PASSED"
                    if target_reached
                    else "IN_PROGRESS"
                )
            )
        else:
            evaluation_status = (
                "NOT_APPLICABLE"
            )

        self._state[
            "evaluation_status"
        ] = evaluation_status

        self._state[
            "unrealized_pnl"
        ] = unrealized_pnl

        self._state[
            "total_pnl"
        ] = total_pnl

        self._state[
            "drawdown"
        ] = drawdown

        self._state[
            "remaining_drawdown_capacity"
        ] = remaining_drawdown_capacity

        self._state[
            "open_positions"
        ] = open_positions

        self._state[
            "closed_positions"
        ] = closed_positions

        blocking_reasons = [
            reason
            for reason in self._state[
                "blocking_reasons"
            ]
            if reason
            != "maximum_total_drawdown_reached"
        ]

        if (
            drawdown
            >= self.maximum_total_drawdown
        ):
            blocking_reasons.append(
                "maximum_total_drawdown_reached"
            )

        self._state[
            "blocking_reasons"
        ] = blocking_reasons

        self._state[
            "trading_blocked"
        ] = bool(
            blocking_reasons
        )

        return {
            "updated": True,
            "status": "UPDATED",
            "state": self.get_state(),
        }

    def update_open_risk(
        self,
        *,
        open_risk: float,
    ) -> dict[str, object]:

        open_risk = float(
            open_risk
        )

        if open_risk < 0:
            raise ValueError(
                "open_risk no puede ser negativo."
            )

        self._state[
            "open_risk"
        ] = open_risk

        return {
            "updated": True,
            "state": self.get_state(),
        }

    def record_daily_pnl(
        self,
        *,
        daily_pnl: float,
    ) -> dict[str, object]:

        daily_pnl = float(
            daily_pnl
        )

        daily_loss_used = max(
            0.0,
            -daily_pnl,
        )

        remaining = (
            None
            if self.maximum_daily_loss is None
            else max(
                0.0,
                self.maximum_daily_loss
                - daily_loss_used,
            )
        )

        self._state[
            "daily_pnl"
        ] = daily_pnl

        self._state[
            "daily_loss_used"
        ] = daily_loss_used

        self._state[
            "remaining_daily_loss_capacity"
        ] = remaining

        reasons = [
            r
            for r in self._state[
                "blocking_reasons"
            ]
            if r != "daily_loss_limit_reached"
        ]

        if (
            self.maximum_daily_loss is not None
            and daily_loss_used
            >= self.maximum_daily_loss
        ):
            reasons.append(
                "daily_loss_limit_reached"
            )

        self._state[
            "blocking_reasons"
        ] = reasons

        self._state[
            "trading_blocked"
        ] = bool(
            reasons
        )

        return {
            "updated": True,
            "state": self.get_state(),
        }

    def reset_daily_state(
        self,
    ) -> dict[str, object]:

        self._state[
            "daily_pnl"
        ] = 0.0

        self._state[
            "daily_loss_used"
        ] = 0.0

        self._state[
            "remaining_daily_loss_capacity"
        ] = (
            self.maximum_daily_loss
        )

        self._state[
            "blocking_reasons"
        ] = [
            r
            for r in self._state[
                "blocking_reasons"
            ]
            if r
            != "daily_loss_limit_reached"
        ]

        self._state[
            "trading_blocked"
        ] = bool(
            self._state[
                "blocking_reasons"
            ]
        )

        return {
            "reset": True,
            "state": self.get_state(),
        }

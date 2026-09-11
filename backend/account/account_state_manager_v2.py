from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from datetime import date, datetime, timezone
from functools import wraps
from math import isfinite
from threading import RLock

from backend.services.market_hours_service_v2 import MarketHoursServiceV2


def _locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


class AccountStateManagerV2:

    def __init__(
        self,
        *,
        starting_balance: float,
        maximum_daily_loss: float | None,
        maximum_total_drawdown: float,
        profit_target: float | None = None,
        account_stage: str | None = None,
        clock: Callable[[], datetime] | None = None,
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

        self._lock = RLock()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._state = {
            "trading_day": MarketHoursServiceV2.trading_day_for(self._clock()).isoformat(),
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

    @_locked
    def get_state(
        self,
    ) -> dict[str, object]:
        return deepcopy(
            self._state
        )

    @_locked
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

        self.ensure_trading_day()
        self._preserve_unclassified_block()

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

        # Portfolio totals are cumulative. Only newly realized PnL belongs
        # in this day's account state; replaying the same summary adds zero.
        daily_pnl = round(
            float(self._state["daily_pnl"])
            + realized_pnl
            - float(self._state["realized_pnl"]),
            10,
        )

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

        self._record_daily_pnl(daily_pnl=daily_pnl)

        return {
            "updated": True,
            "status": "UPDATED",
            "state": self.get_state(),
        }

    @_locked
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

    @_locked
    def record_daily_pnl(
        self,
        *,
        daily_pnl: float,
    ) -> dict[str, object]:

        daily_pnl = float(
            daily_pnl
        )

        self.ensure_trading_day()
        self._preserve_unclassified_block()

        return self._record_daily_pnl(daily_pnl=daily_pnl)

    def _record_daily_pnl(self, *, daily_pnl: float) -> dict[str, object]:
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

    @_locked
    def reset_daily_state(
        self,
    ) -> dict[str, object]:
        day = MarketHoursServiceV2.trading_day_for(self._clock()).isoformat()
        previous = self._state["trading_day"]
        if day < previous:
            raise ValueError("Trading day clock moved backwards; admission denied.")
        if day == previous:
            return {"reset": False, "state": self.get_state()}
        self._preserve_unclassified_block()
        self._state["trading_day"] = day
        # Keep realized_pnl as the synchronization baseline. The next
        # portfolio update must not rebook realizations from previous days.

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

    def ensure_trading_day(self) -> dict[str, object]:
        """Advance at first operational use; reads and snapshot capture stay pure."""
        return self.reset_daily_state()

    def _preserve_unclassified_block(self) -> None:
        if self._state["trading_blocked"] and not self._state["blocking_reasons"]:
            self._state["blocking_reasons"] = ["unclassified_trading_block"]

    @_locked
    def capture_state(self) -> dict[str, object]:
        return {
            "state": self.get_state(),
            "maximum_daily_loss": self.maximum_daily_loss,
            "maximum_total_drawdown": self.maximum_total_drawdown,
        }

    @_locked
    def restore_state(self, *, snapshot: dict[str, object]) -> None:
        """Restore the dated state without resetting or replaying portfolio PnL."""
        if not isinstance(snapshot, dict):
            raise ValueError("Missing account risk snapshot.")
        if (snapshot.get("maximum_daily_loss") != self.maximum_daily_loss
                or snapshot.get("maximum_total_drawdown") != self.maximum_total_drawdown):
            raise ValueError("Account risk snapshot limits do not match.")
        state = deepcopy(snapshot.get("state"))
        if not isinstance(state, dict) or set(state) != set(self._state):
            raise ValueError("Incomplete account risk snapshot.")
        day = state["trading_day"]
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError("Invalid trading_day.")
        for key, value in self._state.items():
            saved = state[key]
            if isinstance(value, bool):
                if not isinstance(saved, bool):
                    raise ValueError(f"Invalid account field: {key}")
            elif isinstance(value, (int, float)):
                if isinstance(saved, bool) or not isinstance(saved, (int, float)) or not isfinite(saved):
                    raise ValueError(f"Invalid account field: {key}")
        for key in ("starting_balance", "account_stage", "profit_target"):
            if state[key] != self._state[key]:
                raise ValueError(f"Account snapshot mismatch: {key}")
        reasons = state["blocking_reasons"]
        if not isinstance(reasons, list) or any(not isinstance(r, str) or not r for r in reasons):
            raise ValueError("Invalid account blocking reasons.")
        loss = max(0.0, -state["daily_pnl"])
        remaining = None if self.maximum_daily_loss is None else max(0.0, self.maximum_daily_loss - loss)
        if state["daily_loss_used"] != loss or state["remaining_daily_loss_capacity"] != remaining:
            raise ValueError("Inconsistent daily risk snapshot.")
        required = []
        if self.maximum_daily_loss is not None and loss >= self.maximum_daily_loss:
            required.append("daily_loss_limit_reached")
        if state["drawdown"] >= self.maximum_total_drawdown:
            required.append("maximum_total_drawdown_reached")
        if any(r not in reasons for r in required) or (reasons and not state["trading_blocked"]):
            raise ValueError("Inconsistent account risk blocks.")
        if (state["balance"] != round(state["starting_balance"] + state["realized_pnl"], 10)
                or state["equity"] != round(state["balance"] + state["unrealized_pnl"], 10)
                or state["drawdown"] != round(max(0.0, state["peak_equity"] - state["equity"]), 10)):
            raise ValueError("Inconsistent account financial snapshot.")
        self._state = state

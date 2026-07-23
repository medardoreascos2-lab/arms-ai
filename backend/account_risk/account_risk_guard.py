from __future__ import annotations

from typing import Any


class AccountRiskGuard:
    """
    Evalúa si una nueva operación puede abrirse
    según los límites globales de la cuenta.
    """

    def __init__(
        self,
        *,
        daily_loss_limit: float,
        max_trades_per_day: int,
        max_consecutive_losses: int,
        max_open_positions: int,
        max_risk_per_trade: float,
    ) -> None:
        if daily_loss_limit <= 0:
            raise ValueError(
                "daily_loss_limit debe ser mayor que cero."
            )

        if max_trades_per_day <= 0:
            raise ValueError(
                "max_trades_per_day debe ser mayor que cero."
            )

        if max_consecutive_losses <= 0:
            raise ValueError(
                "max_consecutive_losses debe ser mayor que cero."
            )

        if max_open_positions <= 0:
            raise ValueError(
                "max_open_positions debe ser mayor que cero."
            )

        if max_risk_per_trade <= 0:
            raise ValueError(
                "max_risk_per_trade debe ser mayor que cero."
            )

        self.daily_loss_limit = float(
            daily_loss_limit
        )

        self.max_trades_per_day = int(
            max_trades_per_day
        )

        self.max_consecutive_losses = int(
            max_consecutive_losses
        )

        self.max_open_positions = int(
            max_open_positions
        )

        self.max_risk_per_trade = float(
            max_risk_per_trade
        )

    def evaluate(
        self,
        *,
        trades_today: list[dict[str, Any]],
        open_positions: int,
        proposed_risk: float,
    ) -> dict[str, object]:
        if proposed_risk < 0:
            raise ValueError(
                "proposed_risk no puede ser negativo."
            )

        if open_positions < 0:
            raise ValueError(
                "open_positions no puede ser negativo."
            )

        pnl_values = [
            float(
                trade["pnl"]
            )
            for trade in trades_today
        ]

        daily_pnl = sum(
            pnl_values
        )

        trade_count = len(
            trades_today
        )

        consecutive_losses = (
            self._count_consecutive_losses(
                pnl_values
            )
        )

        reasons: list[str] = []

        if (
            daily_pnl
            <= -self.daily_loss_limit
        ):
            reasons.append(
                "daily_loss_limit"
            )

        if (
            trade_count
            >= self.max_trades_per_day
        ):
            reasons.append(
                "max_trades_per_day"
            )

        if (
            consecutive_losses
            >= self.max_consecutive_losses
        ):
            reasons.append(
                "max_consecutive_losses"
            )

        if (
            open_positions
            >= self.max_open_positions
        ):
            reasons.append(
                "max_open_positions"
            )

        if (
            proposed_risk
            > self.max_risk_per_trade
        ):
            reasons.append(
                "max_risk_per_trade"
            )

        approved = not reasons

        return {
            "approved": approved,
            "status": (
                "APPROVED"
                if approved
                else "BLOCKED"
            ),
            "daily_pnl": daily_pnl,
            "trade_count": trade_count,
            "consecutive_losses": consecutive_losses,
            "open_positions": open_positions,
            "proposed_risk": proposed_risk,
            "reasons": reasons,
        }

    def _count_consecutive_losses(
        self,
        pnl_values: list[float],
    ) -> int:
        consecutive_losses = 0

        for pnl in reversed(
            pnl_values
        ):
            if pnl < 0:
                consecutive_losses += 1
                continue

            break

        return consecutive_losses

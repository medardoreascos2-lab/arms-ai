from __future__ import annotations

from typing import Any

from backend.models.trade_plan import TradePlan

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


class BacktestTradePlanAdapterV2:
    """
    Convierte una TradingDecisionV2 y una vela
    de backtesting en un trade plan compatible
    con SignalGeneratorV2.
    """

    _REQUIRED_METADATA_FIELDS = (
        "stop_loss",
        "take_profit",
        "contracts",
        "confluence_score",
        "grade",
    )

    def build_trade_plan(
        self,
        *,
        decision: TradingDecisionV2,
        candle: dict[str, Any],
    ) -> TradePlan:

        if not isinstance(
            decision,
            TradingDecisionV2,
        ):
            raise TypeError(
                "decision debe ser TradingDecisionV2."
            )

        if not isinstance(
            candle,
            dict,
        ):
            raise TypeError(
                "candle debe ser un dict."
            )

        if decision.action is TradingActionV2.HOLD:
            raise ValueError(
                "No se puede construir un trade plan "
                "para una decisión HOLD."
            )

        entry_price = float(
            candle.get(
                "close",
                0.0,
            )
        )

        if entry_price <= 0:
            raise ValueError(
                "candle debe contener un close "
                "mayor que cero."
            )

        metadata = decision.metadata

        missing_fields = [
            field
            for field in self._REQUIRED_METADATA_FIELDS
            if field not in metadata
        ]

        if missing_fields:
            raise ValueError(
                "decision.metadata incompleto: "
                + ", ".join(
                    missing_fields
                )
            )

        stop_loss = float(
            metadata["stop_loss"]
        )

        take_profit = float(
            metadata["take_profit"]
        )

        contracts = int(
            metadata["contracts"]
        )

        confluence_score = float(
            metadata["confluence_score"]
        )

        grade = str(
            metadata["grade"]
        ).strip().upper()

        if contracts <= 0:
            raise ValueError(
                "contracts debe ser mayor que cero."
            )

        if not (
            0.0 <= confluence_score <= 1.0
        ):
            raise ValueError(
                "confluence_score debe estar "
                "entre 0.0 y 1.0."
            )

        if not grade:
            raise ValueError(
                "grade no puede estar vacío."
            )

        if decision.action is TradingActionV2.BUY:
            direction = "LONG"
            source_decision = "EXECUTE_LONG"

            if not (
                stop_loss
                < entry_price
                < take_profit
            ):
                raise ValueError(
                    "Los niveles LONG deben cumplir: "
                    "stop_loss < entry_price "
                    "< take_profit."
                )

        else:
            direction = "SHORT"
            source_decision = "EXECUTE_SHORT"

            if not (
                take_profit
                < entry_price
                < stop_loss
            ):
                raise ValueError(
                    "Los niveles SHORT deben cumplir: "
                    "take_profit < entry_price "
                    "< stop_loss."
                )

        risk_points = abs(
            entry_price
            - stop_loss
        )

        reward_points = abs(
            take_profit
            - entry_price
        )

        reward_risk_ratio = round(
            reward_points / risk_points,
            4,
        )

        return TradePlan(
            symbol=str(
                candle.get(
                    "symbol",
                    "NQ",
                )
            ),
            timeframe=str(
                candle.get(
                    "timeframe",
                    "1m",
                )
            ),
            decision=source_decision,
            confidence=str(
                decision.confidence
            ),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            contracts=contracts,
            risk_amount=(
                risk_points * contracts
            ),
            authorized=True,
            probability=float(
                decision.confidence
            ),
            confluence_score=confluence_score,
            grade=grade,
            reasons=[
                f"Grade {grade}",
                f"Confluence {confluence_score}",
                f"RR {reward_risk_ratio}",
            ],
        )

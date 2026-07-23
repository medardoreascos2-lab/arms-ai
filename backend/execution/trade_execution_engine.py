from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


class TradeExecutionEngine:
    """
    Ejecuta una señal aprobada en modo
    simulado.
    """

    SUPPORTED_MODES = {
        "SIMULATED",
    }

    REQUIRED_FIELDS = (
        "symbol",
        "timeframe",
        "action",
        "accepted",
        "status",
        "entry_price",
        "stop_loss",
        "take_profit",
        "generated_at",
    )

    def __init__(
        self,
        *,
        mode: str = "SIMULATED",
    ) -> None:
        mode = mode.strip().upper()

        if mode not in self.SUPPORTED_MODES:
            raise ValueError(
                "mode no soportado."
            )

        self.mode = mode

    def execute(
        self,
        execution: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_execution(
            execution
        )

        if not execution["accepted"]:
            raise ValueError(
                "accepted debe ser True."
            )

        if (
            str(execution["status"])
            .strip()
            .upper()
            != "ACCEPTED"
        ):
            raise ValueError(
                "status debe ser ACCEPTED."
            )

        action = (
            str(execution["action"])
            .strip()
            .upper()
        )

        if action not in {
            "BUY",
            "SELL",
        }:
            raise ValueError(
                "action inválida."
            )

        result = deepcopy(
            execution
        )

        result["mode"] = self.mode
        result["status"] = "SIMULATED"
        result["executed"] = True
        result["executed_at"] = (
            datetime.now(
                timezone.utc
            )
        )

        return result

    def _validate_execution(
        self,
        execution: dict[str, Any],
    ) -> None:
        if not isinstance(
            execution,
            dict,
        ):
            raise TypeError(
                "execution debe ser un diccionario."
            )

        for field in self.REQUIRED_FIELDS:
            if field not in execution:
                raise KeyError(
                    field
                )

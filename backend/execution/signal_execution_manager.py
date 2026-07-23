from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any


class SignalExecutionManager:
    """
    Decide si una señal debe ejecutarse o
    descartarse para evitar duplicados y spam.
    """

    def __init__(
        self,
        *,
        cooldown_minutes: int = 15,
    ) -> None:
        if cooldown_minutes < 0:
            raise ValueError(
                "cooldown_minutes debe ser mayor o igual a cero."
            )

        self.cooldown = timedelta(
            minutes=cooldown_minutes
        )

        self._last_signals: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

    def evaluate(
        self,
        signal: dict[str, Any],
    ) -> dict[str, Any]:
        action = str(
            signal["action"]
        ).strip().upper()

        approved = bool(
            signal["approved"]
        )

        if action == "WAIT":
            return {
                **deepcopy(signal),
                "accepted": False,
                "status": "REJECTED",
                "reason": "WAIT signal",
            }

        if not approved:
            return {
                **deepcopy(signal),
                "accepted": False,
                "status": "REJECTED",
                "reason": "Signal not approved",
            }

        key = (
            str(signal["symbol"]).strip().upper(),
            str(signal["timeframe"]).strip().lower(),
        )

        generated_at = signal["generated_at"]

        previous = self._last_signals.get(
            key
        )

        if previous is not None:
            previous_action = previous["action"]

            previous_time: datetime = previous[
                "generated_at"
            ]

            if (
                previous_action == action
                and generated_at - previous_time
                < self.cooldown
            ):
                return {
                    **deepcopy(signal),
                    "accepted": False,
                    "status": "DUPLICATE",
                    "reason": (
                        "Signal inside cooldown"
                    ),
                }

        self._last_signals[key] = deepcopy(
            signal
        )

        return {
            **deepcopy(signal),
            "accepted": True,
            "status": "ACCEPTED",
        }

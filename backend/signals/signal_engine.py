from __future__ import annotations

from typing import Any


class SignalEngine:
    """
    Convierte un análisis de mercado en una señal final.

    Acciones permitidas:
    - BUY
    - SELL
    - WAIT
    """

    REQUIRED_SECTIONS = (
        "symbol",
        "timeframe",
        "current_price",
        "decision",
        "probability",
        "risk",
        "trade",
    )

    def generate(
        self,
        analysis: dict[str, Any],
    ) -> dict[str, object]:
        self._validate_analysis(
            analysis
        )

        decision = analysis["decision"]
        probability = analysis["probability"]
        risk = analysis["risk"]
        trade = analysis["trade"]

        raw_action = str(
            decision["action"]
        ).strip().upper()

        valid_action = raw_action in {
            "BUY",
            "SELL",
        }

        approved = all(
            (
                bool(decision["approved"]),
                bool(probability["approved"]),
                bool(risk["approved"]),
                valid_action,
            )
        )

        action = (
            raw_action
            if approved
            else "WAIT"
        )

        entry_price = self._optional_float(
            trade["entry_price"]
        )

        stop_loss = self._optional_float(
            trade["stop_loss"]
        )

        take_profit = self._optional_float(
            trade["take_profit"]
        )

        if approved and (
            entry_price is None
            or stop_loss is None
            or take_profit is None
        ):
            raise ValueError(
                "Una señal aprobada requiere "
                "entry_price, stop_loss y "
                "take_profit válidos."
            )

        return {
            "symbol": str(
                analysis["symbol"]
            ).strip().upper(),
            "timeframe": str(
                analysis["timeframe"]
            ).strip().lower(),
            "current_price": float(
                analysis["current_price"]
            ),
            "action": action,
            "approved": approved,
            "score": float(
                decision["score"]
            ),
            "grade": str(
                decision["grade"]
            ),
            "probability": float(
                probability["value"]
            ),
            "confidence": str(
                probability["confidence"]
            ),
            "risk_approved": bool(
                risk["approved"]
            ),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reason": self._build_reason(
                action=action,
                decision_approved=bool(
                    decision["approved"]
                ),
                probability_approved=bool(
                    probability["approved"]
                ),
                risk_approved=bool(
                    risk["approved"]
                ),
                valid_action=valid_action,
            ),
        }

    def _optional_float(
        self,
        value: Any,
    ) -> float | None:
        if value is None:
            return None

        return float(
            value
        )

    def _validate_analysis(
        self,
        analysis: dict[str, Any],
    ) -> None:
        for section in self.REQUIRED_SECTIONS:
            if section not in analysis:
                raise KeyError(
                    section
                )

        required_nested = {
            "decision": (
                "action",
                "score",
                "grade",
                "approved",
            ),
            "probability": (
                "value",
                "confidence",
                "approved",
            ),
            "risk": (
                "approved",
            ),
            "trade": (
                "entry_price",
                "stop_loss",
                "take_profit",
            ),
        }

        for section, fields in required_nested.items():
            content = analysis[section]

            if not isinstance(
                content,
                dict,
            ):
                raise TypeError(
                    f"{section} debe ser un diccionario."
                )

            for field in fields:
                if field not in content:
                    raise KeyError(
                        f"{section}.{field}"
                    )

    def _build_reason(
        self,
        *,
        action: str,
        decision_approved: bool,
        probability_approved: bool,
        risk_approved: bool,
        valid_action: bool,
    ) -> str:
        if action in {
            "BUY",
            "SELL",
        }:
            return (
                "Señal aprobada por decisión, "
                "probabilidad y gestión de riesgo."
            )

        reasons: list[str] = []

        if not valid_action:
            reasons.append(
                "acción no válida"
            )

        if not decision_approved:
            reasons.append(
                "decisión no aprobada"
            )

        if not probability_approved:
            reasons.append(
                "probabilidad no aprobada"
            )

        if not risk_approved:
            reasons.append(
                "riesgo bloqueado"
            )

        return (
            "WAIT: "
            + ", ".join(reasons)
            + "."
        )

from __future__ import annotations


class ExitDecisionEngine:
    """
    Recomienda HOLD, PROTECT o EXIT
    según momentum, beneficio no realizado
    y estructura adversa.
    """

    def __init__(
        self,
        *,
        hold_momentum_threshold: float,
        exit_momentum_threshold: float,
        protect_min_profit_points: float,
    ) -> None:
        if not (
            0.0
            <= hold_momentum_threshold
            <= 1.0
        ):
            raise ValueError(
                "hold_momentum_threshold "
                "debe estar entre 0 y 1."
            )

        if not (
            -1.0
            <= exit_momentum_threshold
            <= 0.0
        ):
            raise ValueError(
                "exit_momentum_threshold "
                "debe estar entre -1 y 0."
            )

        if protect_min_profit_points < 0:
            raise ValueError(
                "protect_min_profit_points "
                "no puede ser negativo."
            )

        self.hold_momentum_threshold = float(
            hold_momentum_threshold
        )

        self.exit_momentum_threshold = float(
            exit_momentum_threshold
        )

        self.protect_min_profit_points = float(
            protect_min_profit_points
        )

    def evaluate(
        self,
        *,
        directional_momentum: float,
        unrealized_points: float,
        adverse_structure: bool,
    ) -> dict[str, object]:
        momentum = float(
            directional_momentum
        )

        if not (
            -1.0
            <= momentum
            <= 1.0
        ):
            raise ValueError(
                "directional_momentum "
                "debe estar entre -1 y 1."
            )

        unrealized = float(
            unrealized_points
        )

        if (
            adverse_structure
            and momentum
            <= self.exit_momentum_threshold
        ):
            return {
                "decision": "EXIT",
                "confidence": abs(
                    momentum
                ),
                "reason": (
                    "Momentum contrario y "
                    "estructura adversa"
                ),
            }

        if (
            adverse_structure
            and unrealized
            >= self.protect_min_profit_points
        ):
            return {
                "decision": "PROTECT",
                "confidence": min(
                    1.0,
                    max(
                        0.0,
                        1.0 - abs(momentum),
                    ),
                ),
                "reason": (
                    "Estructura adversa "
                    "con ganancia"
                ),
            }

        if (
            unrealized
            >= self.protect_min_profit_points
            and momentum
            < self.hold_momentum_threshold
        ):
            return {
                "decision": "PROTECT",
                "confidence": min(
                    1.0,
                    max(
                        0.0,
                        1.0 - abs(momentum),
                    ),
                ),
                "reason": (
                    "Momentum debilitándose "
                    "con ganancia"
                ),
            }

        if (
            momentum
            >= self.hold_momentum_threshold
        ):
            return {
                "decision": "HOLD",
                "confidence": min(
                    1.0,
                    max(
                        0.0,
                        momentum,
                    ),
                ),
                "reason": (
                    "Momentum favorable"
                ),
            }

        return {
            "decision": "HOLD",
            "confidence": min(
                1.0,
                max(
                    0.0,
                    1.0 - abs(momentum),
                ),
            ),
            "reason": (
                "Sin confirmación de salida"
            ),
        }

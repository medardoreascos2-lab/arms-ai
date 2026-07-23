from __future__ import annotations


class ProbabilityEngineV2:
    """
    Calcula una probabilidad ponderada usando:

    - Smart Money
    - Tendencia
    - Régimen de mercado
    - Confluencia
    - Volumen

    También aplica bloqueos por riesgo,
    position sizing y mercado no operable.
    """

    WEIGHTS: dict[str, float] = {
        "smart_money": 0.40,
        "trend": 0.20,
        "market_regime": 0.15,
        "confluence": 0.15,
        "volume": 0.10,
    }

    def __init__(
        self,
        *,
        minimum_approval_probability: float,
        very_high_threshold: float,
        high_threshold: float,
        medium_threshold: float,
    ) -> None:
        minimum_approval = float(
            minimum_approval_probability
        )
        very_high = float(
            very_high_threshold
        )
        high = float(
            high_threshold
        )
        medium = float(
            medium_threshold
        )

        thresholds = {
            "minimum_approval_probability": (
                minimum_approval
            ),
            "very_high_threshold": (
                very_high
            ),
            "high_threshold": high,
            "medium_threshold": medium,
        }

        for field_name, value in thresholds.items():
            if not (
                0.0
                <= value
                <= 1.0
            ):
                raise ValueError(
                    f"{field_name} threshold "
                    "debe estar entre 0 y 1."
                )

        if not (
            medium
            <= high
            <= very_high
        ):
            raise ValueError(
                "El orden de threshold "
                "es inválido."
            )

        if minimum_approval < high:
            raise ValueError(
                "minimum_approval_probability "
                "threshold no puede ser menor "
                "que high_threshold."
            )

        if minimum_approval > very_high:
            raise ValueError(
                "minimum_approval_probability "
                "threshold no puede ser mayor "
                "que very_high_threshold."
            )

        self.minimum_approval_probability = (
            minimum_approval
        )
        self.very_high_threshold = (
            very_high
        )
        self.high_threshold = high
        self.medium_threshold = medium

    def evaluate(
        self,
        *,
        smart_money_score: float,
        trend_score: float,
        market_regime_score: float,
        confluence_score: float,
        volume_score: float,
        risk_approved: bool,
        sizing_approved: bool,
        market_tradable: bool,
    ) -> dict[str, object]:
        components = {
            "smart_money_score": float(
                smart_money_score
            ),
            "trend_score": float(
                trend_score
            ),
            "market_regime_score": float(
                market_regime_score
            ),
            "confluence_score": float(
                confluence_score
            ),
            "volume_score": float(
                volume_score
            ),
        }

        for field_name, value in components.items():
            if not (
                0.0
                <= value
                <= 1.0
            ):
                raise ValueError(
                    f"{field_name} debe estar "
                    "entre 0 y 1."
                )

        raw_contributions = {
            "smart_money": (
                components[
                    "smart_money_score"
                ]
                * self.WEIGHTS[
                    "smart_money"
                ]
            ),
            "trend": (
                components["trend_score"]
                * self.WEIGHTS["trend"]
            ),
            "market_regime": (
                components[
                    "market_regime_score"
                ]
                * self.WEIGHTS[
                    "market_regime"
                ]
            ),
            "confluence": (
                components[
                    "confluence_score"
                ]
                * self.WEIGHTS[
                    "confluence"
                ]
            ),
            "volume": (
                components["volume_score"]
                * self.WEIGHTS["volume"]
            ),
        }

        probability = round(
            sum(
                raw_contributions.values()
            ),
            4,
        )

        contributions = {
            key: round(
                value,
                4,
            )
            for key, value
            in raw_contributions.items()
        }

        if (
            probability
            >= self.very_high_threshold
        ):
            confidence = "VERY_HIGH"
            grade = "A+"
        elif (
            probability
            >= self.high_threshold
        ):
            confidence = "HIGH"
            grade = "A"
        elif (
            probability
            >= self.medium_threshold
        ):
            confidence = "MEDIUM"
            grade = "B"
        else:
            confidence = "LOW"
            grade = "C"

        blocking_reasons: list[str] = []

        if not risk_approved:
            blocking_reasons.append(
                "account_risk_rejected"
            )

        if not sizing_approved:
            blocking_reasons.append(
                "position_sizing_rejected"
            )

        if not market_tradable:
            blocking_reasons.append(
                "market_not_tradable"
            )

        if blocking_reasons:
            approved = False
            decision = "BLOCK"
            status = "BLOCKED"

        elif (
            probability
            >= self.minimum_approval_probability
        ):
            approved = True
            decision = "EXECUTE"
            status = "APPROVED"

        elif (
            probability
            >= self.medium_threshold
        ):
            approved = False
            decision = "WAIT"
            status = "WAITING"

        else:
            approved = False
            decision = "REJECT"
            status = "REJECTED"

        return {
            "approved": approved,
            "decision": decision,
            "status": status,
            "probability": probability,
            "confidence": confidence,
            "grade": grade,
            "inputs": {
                "smart_money_score": (
                    components[
                        "smart_money_score"
                    ]
                ),
                "trend_score": (
                    components[
                        "trend_score"
                    ]
                ),
                "market_regime_score": (
                    components[
                        "market_regime_score"
                    ]
                ),
                "confluence_score": (
                    components[
                        "confluence_score"
                    ]
                ),
                "volume_score": (
                    components[
                        "volume_score"
                    ]
                ),
                "risk_approved": bool(
                    risk_approved
                ),
                "sizing_approved": bool(
                    sizing_approved
                ),
                "market_tradable": bool(
                    market_tradable
                ),
            },
            "contributions": (
                contributions
            ),
            "weights": dict(
                self.WEIGHTS
            ),
            "blocking_reasons": (
                blocking_reasons
            ),
        }

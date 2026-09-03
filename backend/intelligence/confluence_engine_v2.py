from __future__ import annotations


class ConfluenceEngineV2:
    """
    Combina múltiples componentes técnicos
    en una puntuación total de 0 a 100.

    También aplica gates de seguridad:

    - riesgo de cuenta;
    - position sizing;
    - mercado operable.
    """

    # Canonical confluence uses only independent
    # primary market evidence. probability_score
    # remains accepted for call-site compatibility,
    # but it has no scoring authority here.
    _PRIMARY_WEIGHT_SCALE: float = 100.0 / 85.0

    WEIGHTS: dict[str, float] = {
        "trend": 15.0 * _PRIMARY_WEIGHT_SCALE,
        "structure": 15.0 * _PRIMARY_WEIGHT_SCALE,
        "liquidity": 10.0 * _PRIMARY_WEIGHT_SCALE,
        "fvg": 10.0 * _PRIMARY_WEIGHT_SCALE,
        "ema_alignment": 10.0 * _PRIMARY_WEIGHT_SCALE,
        "market_regime": 15.0 * _PRIMARY_WEIGHT_SCALE,
        "volume": 10.0 * _PRIMARY_WEIGHT_SCALE,
    }

    def evaluate(
        self,
        *,
        trend_score: float,
        structure_score: float,
        liquidity_score: float,
        fvg_score: float,
        ema_alignment_score: float,
        market_regime_score: float,
        probability_score: float,
        volume_score: float,
        risk_approved: bool,
        sizing_approved: bool,
        market_tradable: bool,
    ) -> dict[str, object]:
        components = {
            "trend_score": float(
                            trend_score
                        ),
            "structure_score": float(
                            structure_score
                        ),
            "liquidity_score": float(
                            liquidity_score
                        ),
            "fvg_score": float(
                            fvg_score
                        ),
            "ema_alignment_score": float(
                            ema_alignment_score
                        ),
            "market_regime_score": float(
                            market_regime_score
                        ),
            "probability_score": float(
                            probability_score
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

        contributions = {
            "trend": components["trend_score"]
                            * self.WEIGHTS["trend"],
            "structure": components["structure_score"]
                            * self.WEIGHTS["structure"],
            "liquidity": components["liquidity_score"]
                            * self.WEIGHTS["liquidity"],
            "fvg": components["fvg_score"]
                            * self.WEIGHTS["fvg"],
            "ema_alignment": components["ema_alignment_score"]
                            * self.WEIGHTS["ema_alignment"],
            "market_regime": components["market_regime_score"]
                            * self.WEIGHTS["market_regime"],
            "volume": components["volume_score"]
                            * self.WEIGHTS["volume"],
        }

        raw_contributions = dict(
            contributions
        )

        score = round(
            sum(
                raw_contributions.values()
            ),
            2,
        )

        contributions = {
            key: round(
                value,
                2,
            )
            for key, value
            in raw_contributions.items()
        }

        if score >= 90.0:
            grade = "A+"
        elif score >= 80.0:
            grade = "A"
        elif score >= 70.0:
            grade = "B"
        else:
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
            status = "BLOCKED"
            decision = "BLOCK"
        elif grade in {
            "A+",
            "A",
        }:
            approved = True
            status = "APPROVED"
            decision = "EXECUTE"
        elif grade == "B":
            approved = False
            status = "WAITING"
            decision = "WAIT"
        else:
            approved = False
            status = "REJECTED"
            decision = "REJECT"

        return {
            "approved": approved,
            "status": status,
            "decision": decision,
            "score": score,
            "grade": grade,
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

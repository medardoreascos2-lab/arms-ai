from __future__ import annotations


class ExecutionDecisionEngine:
    """
    Centraliza la decisión final de ejecución.

    Decisiones posibles:

    - EXECUTE: todas las condiciones están aprobadas.
    - WAIT: la señal todavía no tiene suficiente calidad.
    - BLOCK: riesgo, sizing o contratos inválidos.
    """

    def __init__(
        self,
        *,
        minimum_confidence: float,
    ) -> None:
        normalized_minimum_confidence = float(
            minimum_confidence
        )

        if not (
            0.0
            <= normalized_minimum_confidence
            <= 1.0
        ):
            raise ValueError(
                "minimum_confidence debe estar "
                "entre 0 y 1."
            )

        self.minimum_confidence = (
            normalized_minimum_confidence
        )

    def evaluate(
        self,
        *,
        signal_accepted: bool,
        signal_confidence: float,
        risk_approved: bool,
        sizing_approved: bool,
        contracts: int,
        market_tradable: bool
        | None = None,
        market_regime: str
        | None = None,
    ) -> dict[str, object]:
        confidence = float(
            signal_confidence
        )

        normalized_contracts = int(
            contracts
        )

        if not (
            0.0
            <= confidence
            <= 1.0
        ):
            raise ValueError(
                "signal_confidence debe estar "
                "entre 0 y 1."
            )

        if normalized_contracts < 0:
            raise ValueError(
                "contracts no puede ser negativo."
            )

        reasons: list[str] = []
        warnings: list[str] = []

        normalized_market_regime = None

        if market_regime is not None:
            normalized_market_regime = (
                str(
                    market_regime
                )
                .strip()
                .upper()
            )

            if not normalized_market_regime:
                normalized_market_regime = None

        if not signal_accepted:
            reasons.append(
                "signal_not_accepted"
            )

        if (
            confidence
            < self.minimum_confidence
        ):
            reasons.append(
                "low_confidence"
            )

        if not risk_approved:
            reasons.append(
                "account_risk_rejected"
            )

        if not sizing_approved:
            reasons.append(
                "position_sizing_rejected"
            )

        if normalized_contracts <= 0:
            reasons.append(
                "invalid_contracts"
            )

        if market_tradable is False:
            reasons.append(
                "market_not_tradable"
            )

        if (
            market_tradable is True
            and normalized_market_regime
            == "RANGE"
        ):
            reasons.append(
                "market_range"
            )

        if (
            market_tradable is True
            and normalized_market_regime
            == "HIGH_VOLATILITY"
        ):
            warnings.append(
                "high_volatility"
            )

        blocking_reasons = {
            "account_risk_rejected",
            "position_sizing_rejected",
            "invalid_contracts",
            "market_not_tradable",
        }

        has_blocking_reason = any(
            reason in blocking_reasons
            for reason in reasons
        )

        if has_blocking_reason:
            decision = "BLOCK"
        elif reasons:
            decision = "WAIT"
        else:
            decision = "EXECUTE"

        approved = (
            decision == "EXECUTE"
        )

        return {
            "approved": approved,
            "decision": decision,
            "signal_confidence": (
                confidence
            ),
            "minimum_confidence": (
                self.minimum_confidence
            ),
            "contracts": (
                normalized_contracts
            ),
            "market_tradable": (
                market_tradable
            ),
            "market_regime": (
                normalized_market_regime
            ),
            "reasons": reasons,
            "warnings": warnings,
        }

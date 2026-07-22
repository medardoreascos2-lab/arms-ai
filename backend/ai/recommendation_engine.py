from __future__ import annotations

from math import isfinite


class RecommendationEngine:
    """
    Evalúa un portafolio mediante reglas financieras
    determinísticas y genera una puntuación,
    alertas y recomendaciones.
    """

    def analyze(
        self,
        *,
        weights: dict[str, float],
        volatility: float,
        sharpe_ratio: float,
        beta: float,
    ) -> dict[str, object]:
        if not weights:
            raise ValueError(
                "weights no puede estar vacío."
            )

        normalized_weights = {
            str(symbol).strip().upper(): float(weight)
            for symbol, weight
            in weights.items()
        }

        if not all(
            isfinite(value)
            for value in normalized_weights.values()
        ):
            raise ValueError(
                "weights contiene valores inválidos."
            )

        weight_sum = sum(
            normalized_weights.values()
        )

        if abs(weight_sum - 1.0) > 1e-9:
            raise ValueError(
                "weights debe sumar 1.0."
            )

        metrics = (
            volatility,
            sharpe_ratio,
            beta,
        )

        if not all(
            isfinite(float(value))
            for value in metrics
        ):
            raise ValueError(
                "Las métricas contienen valores inválidos."
            )

        alerts: list[str] = []
        recommendations: list[str] = []

        max_asset = max(
            normalized_weights,
            key=normalized_weights.get,
        )

        max_weight = normalized_weights[
            max_asset
        ]

        if max_weight > 0.40:
            alerts.append(
                "Existe una alta concentración "
                f"en {max_asset} "
                f"({max_weight * 100:.1f}%)."
            )

            recommendations.append(
                "Reduce la concentración del activo "
                f"{max_asset} para mejorar "
                "la diversificación."
            )

        if sharpe_ratio < 0.80:
            recommendations.append(
                "El Sharpe Ratio es bajo; "
                "considera optimizar la relación "
                "entre retorno y riesgo."
            )

        if volatility >= 0.30:
            alerts.append(
                "La volatilidad del portafolio "
                "es elevada."
            )

            recommendations.append(
                "Considera incorporar activos "
                "menos volátiles o defensivos."
            )

        if beta >= 1.50:
            alerts.append(
                "El beta indica una sensibilidad "
                "alta frente al mercado."
            )

            recommendations.append(
                "Reduce la exposición a activos "
                "con beta elevado si buscas "
                "un perfil más conservador."
            )

        risk_level = self._classify_risk(
            volatility=volatility,
            beta=beta,
        )

        score = self._calculate_score(
            max_weight=max_weight,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            beta=beta,
        )

        if not recommendations:
            recommendations.append(
                "El portafolio presenta métricas "
                "equilibradas bajo las reglas actuales."
            )

        return {
            "score": score,
            "risk_level": risk_level,
            "recommendations": recommendations,
            "alerts": alerts,
        }

    def _classify_risk(
        self,
        *,
        volatility: float,
        beta: float,
    ) -> str:
        if (
            volatility >= 0.30
            or beta >= 1.50
        ):
            return "high"

        if (
            volatility >= 0.18
            or beta >= 1.10
        ):
            return "moderate"

        return "low"

    def _calculate_score(
        self,
        *,
        max_weight: float,
        volatility: float,
        sharpe_ratio: float,
        beta: float,
    ) -> int:
        score = 100.0

        if max_weight > 0.40:
            score -= min(
                25.0,
                (max_weight - 0.40) * 100.0,
            )

        if volatility > 0.15:
            score -= min(
                25.0,
                (volatility - 0.15) * 100.0,
            )

        if sharpe_ratio < 1.00:
            score -= min(
                25.0,
                (1.00 - sharpe_ratio) * 25.0,
            )

        if beta > 1.00:
            score -= min(
                25.0,
                (beta - 1.00) * 20.0,
            )

        return int(
            round(
                max(
                    0.0,
                    min(
                        100.0,
                        score,
                    ),
                )
            )
        )

from __future__ import annotations

from math import isfinite

from backend.ai.explanation_engine import (
    ExplanationEngine,
)
from backend.ai.recommendation_engine import (
    RecommendationEngine,
)


class AIDecisionEngine:
    """
    Orquesta recomendaciones, alertas,
    puntuación y explicaciones del portafolio.
    """

    REQUIRED_METRICS = {
        "volatility",
        "sharpe_ratio",
        "beta",
        "drawdown",
    }

    def __init__(
        self,
        *,
        recommendation_engine: RecommendationEngine
        | None = None,
        explanation_engine: ExplanationEngine
        | None = None,
    ) -> None:
        self.recommendation_engine = (
            recommendation_engine
            or RecommendationEngine()
        )

        self.explanation_engine = (
            explanation_engine
            or ExplanationEngine()
        )

    def analyze(
        self,
        *,
        weights: dict[str, float],
        metrics: dict[str, float],
    ) -> dict[str, object]:
        normalized_metrics = {
            str(name)
            .strip()
            .lower(): float(value)
            for name, value
            in metrics.items()
        }

        missing_metrics = (
            self.REQUIRED_METRICS
            - set(normalized_metrics)
        )

        if missing_metrics:
            missing_list = ", ".join(
                sorted(missing_metrics)
            )

            raise ValueError(
                "metrics debe incluir: "
                f"{missing_list}."
            )

        if not all(
            isfinite(value)
            for value
            in normalized_metrics.values()
        ):
            raise ValueError(
                "metrics contiene valores inválidos."
            )

        recommendation_result = (
            self.recommendation_engine.analyze(
                weights=weights,
                volatility=normalized_metrics[
                    "volatility"
                ],
                sharpe_ratio=normalized_metrics[
                    "sharpe_ratio"
                ],
                beta=normalized_metrics[
                    "beta"
                ],
            )
        )

        score = int(
            recommendation_result["score"]
        )

        explanations = {
            metric: (
                self.explanation_engine.explain_metric(
                    metric=metric,
                    value=normalized_metrics[
                        metric
                    ],
                )
            )
            for metric
            in (
                "volatility",
                "sharpe_ratio",
                "beta",
                "drawdown",
            )
        }

        explanations[
            "portfolio_score"
        ] = (
            self.explanation_engine.explain_metric(
                metric="portfolio_score",
                value=score,
            )
        )

        risk_level = str(
            recommendation_result[
                "risk_level"
            ]
        )

        summary = self._build_summary(
            score=score,
            risk_level=risk_level,
            alerts=list(
                recommendation_result[
                    "alerts"
                ]
            ),
            recommendations=list(
                recommendation_result[
                    "recommendations"
                ]
            ),
        )

        return {
            "score": score,
            "risk_level": risk_level,
            "alerts": list(
                recommendation_result[
                    "alerts"
                ]
            ),
            "recommendations": list(
                recommendation_result[
                    "recommendations"
                ]
            ),
            "explanations": explanations,
            "summary": summary,
        }

    def _build_summary(
        self,
        *,
        score: int,
        risk_level: str,
        alerts: list[str],
        recommendations: list[str],
    ) -> str:
        alert_count = len(alerts)

        recommendation_count = len(
            recommendations
        )

        return (
            "El portafolio presenta un nivel de "
            f"riesgo {risk_level}, con una "
            f"puntuación de {score}/100. "
            f"Se identificaron {alert_count} alertas "
            f"y {recommendation_count} recomendaciones."
        )

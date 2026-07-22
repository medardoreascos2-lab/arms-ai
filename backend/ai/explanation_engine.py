from __future__ import annotations

from math import isfinite


class ExplanationEngine:
    """
    Convierte métricas financieras en explicaciones
    claras y consistentes.
    """

    SUPPORTED_METRICS = {
        "sharpe_ratio",
        "beta",
        "volatility",
        "drawdown",
        "portfolio_score",
    }

    def explain_metric(
        self,
        *,
        metric: str,
        value: float,
    ) -> dict[str, object]:
        normalized_metric = (
            str(metric)
            .strip()
            .lower()
        )

        if normalized_metric not in self.SUPPORTED_METRICS:
            raise ValueError(
                "metric no reconocido."
            )

        numeric_value = float(value)

        if not isfinite(numeric_value):
            raise ValueError(
                "value contiene un valor inválido."
            )

        classification, explanation = (
            self._build_explanation(
                metric=normalized_metric,
                value=numeric_value,
            )
        )

        return {
            "metric": normalized_metric,
            "value": numeric_value,
            "classification": classification,
            "explanation": explanation,
        }

    def _build_explanation(
        self,
        *,
        metric: str,
        value: float,
    ) -> tuple[str, str]:
        if metric == "sharpe_ratio":
            return self._explain_sharpe(
                value
            )

        if metric == "beta":
            return self._explain_beta(
                value
            )

        if metric == "volatility":
            return self._explain_volatility(
                value
            )

        if metric == "drawdown":
            return self._explain_drawdown(
                value
            )

        return self._explain_portfolio_score(
            value
        )

    def _explain_sharpe(
        self,
        value: float,
    ) -> tuple[str, str]:
        if value >= 2.0:
            return (
                "excellent",
                "El Sharpe Ratio es excelente: "
                "el portafolio genera una relación "
                "muy favorable entre retorno y riesgo.",
            )

        if value >= 1.0:
            return (
                "good",
                "El Sharpe Ratio es bueno: "
                "el retorno obtenido compensa "
                "adecuadamente el riesgo asumido.",
            )

        if value >= 0.0:
            return (
                "low",
                "El Sharpe Ratio es bajo: "
                "la compensación por el riesgo "
                "asumido es limitada.",
            )

        return (
            "negative",
            "El Sharpe Ratio es negativo: "
            "el portafolio no está compensando "
            "el riesgo asumido.",
        )

    def _explain_beta(
        self,
        value: float,
    ) -> tuple[str, str]:
        if value >= 1.5:
            return (
                "high",
                "El beta es alto: el portafolio "
                "puede moverse con mayor intensidad "
                "que el mercado.",
            )

        if value >= 0.8:
            return (
                "moderate",
                "El beta es moderado: el portafolio "
                "mantiene una sensibilidad cercana "
                "a la del mercado.",
            )

        return (
            "low",
            "El beta es bajo: el portafolio "
            "tiende a reaccionar menos que el mercado.",
        )

    def _explain_volatility(
        self,
        value: float,
    ) -> tuple[str, str]:
        if value >= 0.30:
            return (
                "high",
                "La volatilidad es alta: "
                "el portafolio puede experimentar "
                "variaciones importantes.",
            )

        if value >= 0.15:
            return (
                "moderate",
                "La volatilidad es moderada: "
                "existe un nivel de variación "
                "relevante, pero controlable.",
            )

        return (
            "low",
            "La volatilidad es baja: "
            "el comportamiento del portafolio "
            "es relativamente estable.",
        )

    def _explain_drawdown(
        self,
        value: float,
    ) -> tuple[str, str]:
        if value <= -0.20:
            return (
                "severe",
                "La caída máxima es severa: "
                "el portafolio ha sufrido una "
                "pérdida importante desde su máximo.",
            )

        if value <= -0.10:
            return (
                "moderate",
                "La caída máxima es moderada: "
                "el portafolio presenta una "
                "pérdida relevante desde su máximo.",
            )

        return (
            "mild",
            "La caída máxima es limitada: "
            "el portafolio ha mantenido una "
            "recuperación relativamente estable.",
        )

    def _explain_portfolio_score(
        self,
        value: float,
    ) -> tuple[str, str]:
        if value >= 85:
            return (
                "excellent",
                "El portafolio presenta una "
                "calificación excelente bajo "
                "las reglas actuales.",
            )

        if value >= 70:
            return (
                "good",
                "El portafolio presenta una "
                "calificación sólida, con algunos "
                "aspectos que podrían optimizarse.",
            )

        if value >= 50:
            return (
                "moderate",
                "El portafolio presenta una "
                "calificación intermedia y requiere "
                "mejoras en riesgo o diversificación.",
            )

        return (
            "poor",
            "El portafolio presenta una "
            "calificación baja y necesita "
            "una revisión integral.",
        )

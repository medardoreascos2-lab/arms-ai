from dataclasses import dataclass, field
from typing import Dict, List

from backend.intelligence.confluence_engine import ConfluenceResult


@dataclass
class ProbabilityResult:
    probability: float
    confidence: str
    approved: bool
    recommendation: str
    positive_factors: List[str] = field(default_factory=list)
    negative_factors: List[str] = field(default_factory=list)
    adjustments: Dict[str, float] = field(default_factory=dict)


class ProbabilityEngine:
    """
    Convierte el resultado del Confluence Engine en una estimación
    inicial de probabilidad.

    Esta versión se basa en reglas. Más adelante los valores serán
    calibrados mediante backtesting y resultados históricos reales.
    """

    MINIMUM_PROBABILITY = 65.0

    def evaluate(
        self,
        confluence: ConfluenceResult,
    ) -> ProbabilityResult:
        probability = 35.0
        positive_factors: List[str] = []
        negative_factors: List[str] = []
        adjustments: Dict[str, float] = {}

        breakdown = confluence.breakdown

        # Tendencia
        trend_points = breakdown.get("trend", 0.0)

        if trend_points >= 20.0:
            probability += 10.0
            adjustments["trend"] = 10.0
            positive_factors.append("Tendencia principal alineada")
        elif trend_points > 0:
            probability += 3.0
            adjustments["trend"] = 3.0
        else:
            probability -= 8.0
            adjustments["trend"] = -8.0
            negative_factors.append("Tendencia sin confirmación")

        # EMA
        ema_points = breakdown.get("ema", 0.0)

        if ema_points >= 15.0:
            probability += 7.0
            adjustments["ema"] = 7.0
            positive_factors.append("EMA alineada con la dirección")
        elif ema_points == 0:
            probability -= 5.0
            adjustments["ema"] = -5.0
            negative_factors.append("EMA contraria a la operación")

        # Estructura
        structure_points = breakdown.get("structure", 0.0)

        if structure_points >= 15.0:
            probability += 10.0
            adjustments["structure"] = 10.0
            positive_factors.append("Estructura de mercado confirmada")
        elif structure_points == 0:
            probability -= 10.0
            adjustments["structure"] = -10.0
            negative_factors.append("Estructura de mercado contraria")

        # BOS
        bos_points = breakdown.get("bos", 0.0)

        if bos_points >= 15.0:
            probability += 9.0
            adjustments["bos"] = 9.0
            positive_factors.append("BOS confirmado")
        elif bos_points == 0:
            probability -= 7.0
            adjustments["bos"] = -7.0
            negative_factors.append("No existe BOS válido")

        # CHoCH
        choch_points = breakdown.get("choch", 0.0)

        if choch_points >= 10.0:
            probability += 6.0
            adjustments["choch"] = 6.0
            positive_factors.append("CHoCH confirmado")
        elif choch_points == 0:
            probability -= 4.0
            adjustments["choch"] = -4.0
            negative_factors.append("CHoCH contrario")
        else:
            adjustments["choch"] = 0.0

        # Liquidez
        liquidity_points = breakdown.get("liquidity", 0.0)

        if liquidity_points >= 10.0:
            probability += 10.0
            adjustments["liquidity"] = 10.0
            positive_factors.append("Barrido de liquidez confirmado")
        elif liquidity_points >= 7.0:
            probability += 4.0
            adjustments["liquidity"] = 4.0
            positive_factors.append("Reacción parcial de liquidez")
        else:
            probability -= 9.0
            adjustments["liquidity"] = -9.0
            negative_factors.append("No existe confirmación de liquidez")

        # RSI
        rsi_points = breakdown.get("rsi", 0.0)

        if rsi_points >= 5.0:
            probability += 6.0
            adjustments["rsi"] = 6.0
            positive_factors.append("RSI en zona favorable")
        elif rsi_points >= 3.0:
            probability += 2.0
            adjustments["rsi"] = 2.0
        else:
            probability -= 8.0
            adjustments["rsi"] = -8.0
            negative_factors.append("RSI desfavorable o extremo")

        # ATR
        atr_points = breakdown.get("atr", 0.0)

        if atr_points >= 5.0:
            probability += 6.0
            adjustments["atr"] = 6.0
            positive_factors.append("Volatilidad adecuada")
        elif atr_points >= 2.5:
            adjustments["atr"] = 0.0
        else:
            probability -= 6.0
            adjustments["atr"] = -6.0
            negative_factors.append("Volatilidad inadecuada")

        # Riesgo
        risk_points = breakdown.get("risk", 0.0)

        if risk_points >= 5.0:
            probability += 5.0
            adjustments["risk"] = 5.0
            positive_factors.append("Gestión de riesgo aprobada")
        else:
            probability -= 20.0
            adjustments["risk"] = -20.0
            negative_factors.append("Gestión de riesgo rechazada")

        # Penalización si Confluence no aprueba
        if not confluence.approved:
            probability -= 5.0
            adjustments["confluence_filter"] = -5.0
            negative_factors.append(
                "La operación no superó el filtro de confluencia"
            )

        probability = round(
            max(0.0, min(probability, 95.0)),
            2,
        )

        confidence = self._calculate_confidence(probability)

        approved = (
            probability >= self.MINIMUM_PROBABILITY
            and confluence.approved
        )

        if approved:
            recommendation = confluence.direction
        else:
            recommendation = "NO_TRADE"

        return ProbabilityResult(
            probability=probability,
            confidence=confidence,
            approved=approved,
            recommendation=recommendation,
            positive_factors=positive_factors,
            negative_factors=negative_factors,
            adjustments=adjustments,
        )

    def _calculate_confidence(
        self,
        probability: float,
    ) -> str:
        if probability >= 80.0:
            return "MUY ALTA"

        if probability >= 70.0:
            return "ALTA"

        if probability >= 60.0:
            return "MEDIA"

        return "BAJA"
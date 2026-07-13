from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ConfluenceResult:
    score: float
    grade: str
    action: str
    direction: str
    approved: bool
    confirmations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    breakdown: Dict[str, float] = field(default_factory=dict)


class ConfluenceEngine:
    """
    Combina las señales de los diferentes motores de ARMS AI
    y produce una evaluación única de la oportunidad.
    """

    MAX_SCORE = 100.0
    MINIMUM_TRADE_SCORE = 80.0

    def evaluate(
        self,
        trend: Any,
        ema: Any,
        rsi: Any,
        atr: Any,
        structure: Any,
        bos: Any,
        choch: Any,
        liquidity: Any,
        risk: Any,
    ) -> ConfluenceResult:
        score = 0.0
        confirmations: List[str] = []
        warnings: List[str] = []
        breakdown: Dict[str, float] = {}

        normalized_trend = self._normalize_direction(trend)
        normalized_ema = self._normalize_direction(ema)
        normalized_structure = self._normalize_direction(structure)
        normalized_bos = self._normalize_direction(bos)
        normalized_choch = self._normalize_direction(choch)
        normalized_liquidity = self._normalize_direction(liquidity)

        direction = self._determine_direction(
            trend=normalized_trend,
            ema=normalized_ema,
            structure=normalized_structure,
            bos=normalized_bos,
            choch=normalized_choch,
        )

        # 1. Tendencia principal: máximo 20 puntos
        trend_points = self._score_direction_alignment(
            value=normalized_trend,
            expected=direction,
            full_points=20.0,
        )
        breakdown["trend"] = trend_points
        score += trend_points

        if trend_points == 20.0:
            confirmations.append(f"Tendencia alineada: {direction}")
        else:
            warnings.append(
                "La tendencia principal no está completamente alineada"
            )

        # 2. EMAs: máximo 15 puntos
        ema_points = self._score_direction_alignment(
            value=normalized_ema,
            expected=direction,
            full_points=15.0,
        )
        breakdown["ema"] = ema_points
        score += ema_points

        if ema_points == 15.0:
            confirmations.append("EMAs alineadas con la dirección")
        else:
            warnings.append(
                "Las EMAs no confirman completamente la operación"
            )

        # 3. Estructura de mercado: máximo 15 puntos
        structure_points = self._score_direction_alignment(
            value=normalized_structure,
            expected=direction,
            full_points=15.0,
        )
        breakdown["structure"] = structure_points
        score += structure_points

        if structure_points == 15.0:
            confirmations.append("Estructura de mercado confirmada")
        else:
            warnings.append(
                "La estructura de mercado es débil o contraria"
            )

        # 4. BOS: máximo 15 puntos
        bos_points = self._score_direction_alignment(
            value=normalized_bos,
            expected=direction,
            full_points=15.0,
        )
        breakdown["bos"] = bos_points
        score += bos_points

        if bos_points == 15.0:
            confirmations.append("BOS confirmado")
        else:
            warnings.append(
                "No existe un BOS claro en la dirección esperada"
            )

        # 5. CHoCH: máximo 10 puntos
        choch_points = self._score_optional_confirmation(
            value=normalized_choch,
            expected=direction,
            full_points=10.0,
        )
        breakdown["choch"] = choch_points
        score += choch_points

        if choch_points == 10.0:
            confirmations.append("CHoCH confirmado")
        elif choch_points == 0.0:
            warnings.append(
                "CHoCH contrario a la dirección de la operación"
            )

        # 6. Liquidez: máximo 10 puntos
        liquidity_points = self._score_liquidity(
            liquidity=liquidity,
            normalized_liquidity=normalized_liquidity,
            direction=direction,
        )
        breakdown["liquidity"] = liquidity_points
        score += liquidity_points

        if liquidity_points >= 8.0:
            confirmations.append(
                "Barrido o reacción de liquidez confirmado"
            )
        else:
            warnings.append(
                "No existe confirmación suficiente de liquidez"
            )

        # 7. RSI: máximo 5 puntos
        rsi_points = self._score_rsi(
            rsi=rsi,
            direction=direction,
        )
        breakdown["rsi"] = rsi_points
        score += rsi_points

        if rsi_points == 5.0:
            confirmations.append("RSI favorable")
        elif rsi_points == 0.0:
            warnings.append(
                "RSI desfavorable o en zona extrema"
            )

        # 8. ATR / volatilidad: máximo 5 puntos
        atr_points = self._score_atr(atr)
        breakdown["atr"] = atr_points
        score += atr_points

        if atr_points == 5.0:
            confirmations.append("Volatilidad adecuada")
        else:
            warnings.append("La volatilidad no es ideal")

        # 9. Riesgo: máximo 5 puntos y filtro obligatorio
        risk_points, risk_approved = self._score_risk(risk)
        breakdown["risk"] = risk_points
        score += risk_points

        if risk_approved:
            confirmations.append("Gestión de riesgo aprobada")
        else:
            warnings.append(
                "Operación bloqueada por gestión de riesgo"
            )

        score = round(min(score, self.MAX_SCORE), 2)
        grade = self._calculate_grade(score)

        direction_valid = direction in {"BUY", "SELL"}

        approved = (
            score >= self.MINIMUM_TRADE_SCORE
            and risk_approved
            and direction_valid
        )

        action = direction if approved else "NO_TRADE"

        return ConfluenceResult(
            score=score,
            grade=grade,
            action=action,
            direction=direction,
            approved=approved,
            confirmations=confirmations,
            warnings=warnings,
            breakdown=breakdown,
        )

    def _determine_direction(
        self,
        trend: str,
        ema: str,
        structure: str,
        bos: str,
        choch: str,
    ) -> str:
        bullish_votes = 0
        bearish_votes = 0

        values = [
            trend,
            ema,
            structure,
            bos,
            choch,
        ]

        for value in values:
            if value == "BUY":
                bullish_votes += 1
            elif value == "SELL":
                bearish_votes += 1

        if bullish_votes > bearish_votes:
            return "BUY"

        if bearish_votes > bullish_votes:
            return "SELL"

        return "NEUTRAL"

    def _score_direction_alignment(
        self,
        value: str,
        expected: str,
        full_points: float,
    ) -> float:
        if expected == "NEUTRAL":
            return 0.0

        if value == expected:
            return full_points

        if value == "NEUTRAL":
            return full_points * 0.25

        return 0.0

    def _score_optional_confirmation(
        self,
        value: str,
        expected: str,
        full_points: float,
    ) -> float:
        if expected == "NEUTRAL":
            return 0.0

        if value == expected:
            return full_points

        if value == "NEUTRAL":
            return full_points * 0.5

        return 0.0

    def _score_liquidity(
        self,
        liquidity: Any,
        normalized_liquidity: str,
        direction: str,
    ) -> float:
        if direction == "NEUTRAL":
            return 0.0

        if isinstance(liquidity, bool):
            return 10.0 if liquidity else 0.0

        if isinstance(liquidity, dict):
            detected_value = liquidity.get(
                "sweep_detected",
                liquidity.get(
                    "liquidity_sweep",
                    liquidity.get("detected", False),
                ),
            )

            detected = self._normalize_boolean(detected_value)

            liquidity_direction = self._normalize_direction(
                liquidity.get(
                    "direction",
                    liquidity.get("bias", "NEUTRAL"),
                )
            )

            if not detected:
                return 0.0

            if liquidity_direction == direction:
                return 10.0

            if liquidity_direction == "NEUTRAL":
                return 7.0

            return 0.0

        if normalized_liquidity == direction:
            return 10.0

        return 0.0

    def _score_rsi(
        self,
        rsi: Any,
        direction: str,
    ) -> float:
        rsi_value = self._extract_numeric_value(
            rsi,
            keys=("value", "rsi", "current"),
        )

        if rsi_value is None:
            return 2.5

        if direction == "BUY":
            if 45.0 <= rsi_value <= 65.0:
                return 5.0

            if 35.0 <= rsi_value < 45.0:
                return 3.0

            return 0.0

        if direction == "SELL":
            if 35.0 <= rsi_value <= 55.0:
                return 5.0

            if 55.0 < rsi_value <= 65.0:
                return 3.0

            return 0.0

        return 0.0

    def _score_atr(self, atr: Any) -> float:
        if isinstance(atr, bool):
            return 5.0 if atr else 0.0

        if isinstance(atr, dict):
            status = str(
                atr.get(
                    "status",
                    atr.get(
                        "volatility",
                        atr.get("condition", ""),
                    ),
                )
            ).strip().upper()

            normal_statuses = {
                "NORMAL",
                "ADEQUATE",
                "VALID",
                "GOOD",
                "MEDIUM",
                "MEDIA",
                "VOLATILIDAD NORMAL",
                "VOLATILIDAD MEDIA",
                "VOLATILIDAD ADECUADA",
            }

            low_statuses = {
                "LOW",
                "BAJA",
                "VOLATILIDAD BAJA",
            }

            excessive_statuses = {
                "EXTREME",
                "TOO_HIGH",
                "EXCESSIVE",
                "HIGH",
                "ALTA",
                "VOLATILIDAD ALTA",
                "VOLATILIDAD EXTREMA",
            }

            if status in normal_statuses:
                return 5.0

            if status in low_statuses:
                return 1.0

            if status in excessive_statuses:
                return 1.0

            if status:
                return 0.0

        atr_value = self._extract_numeric_value(
            atr,
            keys=("value", "atr", "current"),
        )

        if atr_value is not None and atr_value > 0:
            return 2.5

        return 0.0

    def _score_risk(
        self,
        risk: Any,
    ) -> tuple[float, bool]:
        if isinstance(risk, bool):
            return (5.0, True) if risk else (0.0, False)

        if isinstance(risk, dict):
            approved_value = risk.get(
                "approved",
                risk.get(
                    "is_valid",
                    risk.get(
                        "allowed",
                        risk.get("valid", False),
                    ),
                ),
            )

            approved = self._normalize_boolean(
                approved_value
            )

            return (
                (5.0, True)
                if approved
                else (0.0, False)
            )

        normalized = str(risk).strip().upper()

        if normalized in {
            "APPROVED",
            "VALID",
            "ALLOWED",
            "OK",
            "TRUE",
            "SI",
            "SÍ",
        }:
            return 5.0, True

        return 0.0, False

    def _normalize_boolean(
        self,
        value: Any,
    ) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return value != 0

        normalized = str(value).strip().upper()

        true_values = {
            "TRUE",
            "YES",
            "SI",
            "SÍ",
            "1",
            "DETECTED",
            "CONFIRMED",
            "CONFIRMADO",
        }

        false_values = {
            "FALSE",
            "NO",
            "0",
            "NONE",
            "NINGUNO",
            "NINGUNA",
            "NOT_DETECTED",
            "NO_DETECTADO",
            "",
        }

        if normalized in true_values:
            return True

        if normalized in false_values:
            return False

        return False

    def _normalize_direction(
        self,
        value: Any,
    ) -> str:
        if isinstance(value, dict):
            value = value.get(
                "direction",
                value.get(
                    "trend",
                    value.get(
                        "signal",
                        value.get(
                            "bias",
                            value.get(
                                "action",
                                "NEUTRAL",
                            ),
                        ),
                    ),
                ),
            )

        normalized = str(value).strip().upper()

        bullish_values = {
            "BUY",
            "LONG",
            "BULLISH",
            "ALCISTA",
            "UP",
            "UPTREND",
            "COMPRA",
            "COMPRAR",
        }

        bearish_values = {
            "SELL",
            "SHORT",
            "BEARISH",
            "BAJISTA",
            "DOWN",
            "DOWNTREND",
            "VENTA",
            "VENDER",
        }

        if normalized in bullish_values:
            return "BUY"

        if normalized in bearish_values:
            return "SELL"

        return "NEUTRAL"

    def _extract_numeric_value(
        self,
        data: Any,
        keys: tuple[str, ...],
    ) -> float | None:
        if (
            isinstance(data, (int, float))
            and not isinstance(data, bool)
        ):
            return float(data)

        if isinstance(data, dict):
            for key in keys:
                value = data.get(key)

                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                ):
                    return float(value)

        return None

    def _calculate_grade(
        self,
        score: float,
    ) -> str:
        if score >= 95.0:
            return "A+"

        if score >= 90.0:
            return "A"

        if score >= 80.0:
            return "B"

        if score >= 70.0:
            return "C"

        return "NO_TRADE"
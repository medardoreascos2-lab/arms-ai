from backend.models.reasoning_result import ReasoningResult


class ReasoningEngine:
    A_PLUS_THRESHOLD = 85
    A_THRESHOLD = 70

    def evaluate(
        self,
        trend: str,
        market_structure: str,
        bos_direction: str,
        choch_direction: str,
        liquidity_confirmed: bool,
        rsi_status: str,
        atr_status: str,
        reward_risk_ratio: float,
        risk_allowed: bool,
        session_allowed: bool,
    ) -> ReasoningResult:
        result = ReasoningResult()

        if not risk_allowed:
            result.blockers.append("Riesgo no autorizado.")

        if not session_allowed:
            result.blockers.append("Sesión no autorizada.")

        if result.blockers:
            return result

        buy_score = 0
        sell_score = 0

        if trend == "ALCISTA":
            buy_score += 25
            result.reasons.append("Tendencia alcista.")
        elif trend == "BAJISTA":
            sell_score += 25
            result.reasons.append("Tendencia bajista.")

        if market_structure == "ALCISTA":
            buy_score += 20
            result.reasons.append("Estructura de mercado alcista.")
        elif market_structure == "BAJISTA":
            sell_score += 20
            result.reasons.append("Estructura de mercado bajista.")

        if bos_direction == "ALCISTA":
            buy_score += 15
            result.reasons.append("BOS alcista.")
        elif bos_direction == "BAJISTA":
            sell_score += 15
            result.reasons.append("BOS bajista.")

        if choch_direction == "ALCISTA":
            buy_score += 10
            result.reasons.append("CHoCH alcista.")
        elif choch_direction == "BAJISTA":
            sell_score += 10
            result.reasons.append("CHoCH bajista.")

        if liquidity_confirmed:
            buy_score += 15
            sell_score += 15
            result.reasons.append("Liquidez confirmada.")

        if rsi_status == "NEUTRAL":
            buy_score += 5
            sell_score += 5
            result.reasons.append("RSI neutral.")
        elif rsi_status == "SOBREVENTA":
            buy_score += 5
            result.reasons.append("RSI en sobreventa.")
        elif rsi_status == "SOBRECOMPRA":
            sell_score += 5
            result.reasons.append("RSI en sobrecompra.")

        if atr_status == "VOLATILIDAD MEDIA":
            buy_score += 5
            sell_score += 5
            result.reasons.append("Volatilidad adecuada.")
        elif atr_status == "VOLATILIDAD BAJA":
            result.blockers.append("Volatilidad insuficiente.")
        elif atr_status == "VOLATILIDAD ALTA":
            result.reasons.append("Volatilidad alta: reducir tamaño.")

        if reward_risk_ratio >= 3.0:
            buy_score += 15
            sell_score += 15
            result.reasons.append("Relación riesgo/beneficio excelente.")
        elif reward_risk_ratio >= 2.0:
            buy_score += 10
            sell_score += 10
            result.reasons.append("Relación riesgo/beneficio aceptable.")
        else:
            result.blockers.append(
                "Relación riesgo/beneficio insuficiente."
            )

        result.buy_score = buy_score
        result.sell_score = sell_score
        result.quality_score = max(buy_score, sell_score)

        if result.blockers:
            return result

        if buy_score > sell_score:
            result.direction = "COMPRA"
        elif sell_score > buy_score:
            result.direction = "VENTA"
        else:
            return result

        if result.quality_score >= self.A_PLUS_THRESHOLD:
            result.grade = "A+"
            result.confidence = "ALTA"
            result.authorized = True
        elif result.quality_score >= self.A_THRESHOLD:
            result.grade = "A"
            result.confidence = "MEDIA"
            result.authorized = True

        return result

class TradingIntelligence:
    def __init__(self):
        self.score = 0
        self.confidence = "BAJA"
        self.recommendation = "ESPERAR"
        self.reasons: list[str] = []

    def analyze(
        self,
        trend: str,
        current_price: float,
        ema: float,
        rsi: float,
        rsi_status: str,
        atr: float,
        atr_status: str,
        market_structure: str,
        bos_detected: str,
        bos_direction: str,
    ) -> str:
        self.score = 0
        self.reasons = []

        # Tendencia y EMA
        if trend == "ALCISTA" and current_price > ema:
            self.score += 35
            self.reasons.append(
                "Precio sobre la EMA y tendencia alcista."
            )

        elif trend == "BAJISTA" and current_price < ema:
            self.score -= 35
            self.reasons.append(
                "Precio bajo la EMA y tendencia bajista."
            )

        # RSI
        if rsi_status == "NEUTRAL":
            if trend == "ALCISTA":
                self.score += 20
                self.reasons.append(
                    "RSI neutral permite buscar compras."
                )

            elif trend == "BAJISTA":
                self.score -= 20
                self.reasons.append(
                    "RSI neutral permite buscar ventas."
                )

        elif rsi_status == "SOBRECOMPRA":
            self.score -= 15
            self.reasons.append(
                "RSI en sobrecompra: evitar compras tardías."
            )

        elif rsi_status == "SOBREVENTA":
            self.score += 15
            self.reasons.append(
                "RSI en sobreventa: evitar ventas tardías."
            )

        # Market Structure
        if market_structure == "ALCISTA":
            if trend == "ALCISTA":
                self.score += 15
                self.reasons.append(
                    "La estructura de mercado confirma el sesgo alcista."
                )
            else:
                self.score -= 10
                self.reasons.append(
                    "La estructura alcista contradice la tendencia detectada."
                )

        elif market_structure == "BAJISTA":
            if trend == "BAJISTA":
                self.score -= 15
                self.reasons.append(
                    "La estructura de mercado confirma el sesgo bajista."
                )
            else:
                self.score += 10
                self.reasons.append(
                    "La estructura bajista contradice la tendencia detectada."
                )

        # BOS
        if bos_detected == "SÍ":
            if bos_direction == "ALCISTA" and trend == "ALCISTA":
                self.score += 15
                self.reasons.append(
                    "BOS alcista confirma continuación de estructura."
                )

            elif bos_direction == "BAJISTA" and trend == "BAJISTA":
                self.score -= 15
                self.reasons.append(
                    "BOS bajista confirma continuación de estructura."
                )

            else:
                self.reasons.append(
                    "El BOS contradice la tendencia principal."
                )

        # ATR
        if atr_status == "VOLATILIDAD MEDIA":
            self.reasons.append(
                "Volatilidad adecuada para operar."
            )

        elif atr_status == "VOLATILIDAD ALTA":
            self.reasons.append(
                "Volatilidad alta: reducir riesgo."
            )

        elif atr_status == "VOLATILIDAD BAJA":
            self.reasons.append(
                "Volatilidad baja: menor calidad de oportunidad."
            )

        self._set_recommendation()
        self._set_confidence()

        return self.recommendation

    def _set_recommendation(self) -> None:
        if self.score >= 40:
            self.recommendation = "BUSCAR COMPRAS"

        elif self.score <= -40:
            self.recommendation = "BUSCAR VENTAS"

        else:
            self.recommendation = "ESPERAR"

    def _set_confidence(self) -> None:
        absolute_score = abs(self.score)

        if absolute_score >= 50:
            self.confidence = "ALTA"

        elif absolute_score >= 30:
            self.confidence = "MEDIA"

        else:
            self.confidence = "BAJA"

    def show(self) -> None:
        print("------ TRADING INTELLIGENCE ------")
        print(f"Puntuación: {self.score}")
        print(f"Confianza: {self.confidence}")
        print(f"Recomendación: {self.recommendation}")

        print("Motivos:")
        for reason in self.reasons:
            print(f"- {reason}")
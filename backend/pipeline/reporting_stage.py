from typing import Any


class ReportingStage:
    """
    Presenta en consola los resultados ya calculados por la pipeline.

    Esta etapa no recalcula datos ni modifica decisiones.
    Solo organiza y muestra la salida final.
    """

    REQUIRED_KEYS = (
        "candle_manager",
        "latest_candle",
        "feed",
        "risk_manager",
        "ema",
        "rsi",
        "atr",
        "market_structure",
        "bos",
        "choch",
        "liquidity",
        "trend",
        "intelligence",
        "decision",
        "dynamic_risk",
        "trade_levels",
        "validator",
        "confluence_result",
        "reasoning_result",
        "probability_result",
        "council_result",
        "trade_plan",
        "trade_logger",
        "history_analyzer",
        "execution_simulator",
        "execution_status",
        "simulated_trade",
        "simulated_trade_logger",
    )

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_context(context)

        candle_manager = context["candle_manager"]
        latest_candle = context["latest_candle"]
        feed = context["feed"]
        risk_manager = context["risk_manager"]

        ema = context["ema"]
        rsi = context["rsi"]
        atr = context["atr"]

        market_structure = context["market_structure"]
        bos = context["bos"]
        choch = context["choch"]
        liquidity = context["liquidity"]

        trend = context["trend"]
        intelligence = context["intelligence"]
        decision = context["decision"]

        dynamic_risk = context["dynamic_risk"]
        trade_levels = context["trade_levels"]
        validator = context["validator"]

        confluence_result = context["confluence_result"]
        reasoning_result = context["reasoning_result"]
        probability_result = context["probability_result"]
        council_result = context["council_result"]

        trade_plan = context["trade_plan"]
        trade_logger = context["trade_logger"]
        history_analyzer = context["history_analyzer"]
        execution_status = context["execution_status"]
        simulated_trade = context["simulated_trade"]
        simulated_trade_logger = context["simulated_trade_logger"]

        # ==============================
        # MERCADO
        # ==============================
        candle_manager.show_status()
        latest_candle.show()
        feed.show()

        # ==============================
        # RIESGO BASE
        # ==============================
        risk_manager.show_risk()

        # ==============================
        # INDICADORES
        # ==============================
        ema.show()
        rsi.show()
        atr.show()

        # ==============================
        # SMART MONEY
        # ==============================
        market_structure.show()
        bos.show()
        choch.show()
        liquidity.show()

        # ==============================
        # INTELIGENCIA
        # ==============================
        trend.show()
        intelligence.show()
        decision.show()

        # ==============================
        # RIESGO Y VALIDACIÓN
        # ==============================
        dynamic_risk.show()
        trade_levels.show()
        validator.show()

        # ==============================
        # CONFLUENCIA
        # ==============================
        self._show_confluence(confluence_result)

        # ==============================
        # RAZONAMIENTO
        # ==============================
        reasoning_result.show()

        # ==============================
        # PROBABILIDAD
        # ==============================
        self._show_probability(probability_result)

        # ==============================
        # CONSEJO
        # ==============================
        council_result.show()

        # ==============================
        # PLAN
        # ==============================
        trade_plan.show()

        # ==============================
        # REGISTRO E HISTORIAL
        # ==============================
        trade_logger.show_confirmation()
        history_analyzer.show()

        # ==============================
        # SIMULACIÓN
        # ==============================
        print("------ EXECUTION SIMULATOR ------")

        if simulated_trade is not None:
            simulated_trade.show()

            if simulated_trade_logger is not None:
                simulated_trade_logger.show_confirmation()

        elif execution_status:
            print(execution_status)

        return context

    def _show_confluence(
        self,
        result: Any,
    ) -> None:
        print("------ CONFLUENCE ENGINE ------")
        print(f"Dirección: {result.direction}")
        print(f"Puntuación: {result.score:.2f}/100")
        print(f"Calidad: {result.grade}")
        print(
            "Operación aprobada:",
            "SÍ" if result.approved else "NO",
        )
        print(f"Acción final: {result.action}")

        print("Desglose:")
        for component, points in result.breakdown.items():
            print(f"- {component}: {points:.2f}")

        if result.confirmations:
            print("Confirmaciones:")
            for confirmation in result.confirmations:
                print(f"- {confirmation}")

        if result.warnings:
            print("Advertencias:")
            for warning in result.warnings:
                print(f"- {warning}")

    def _show_probability(
        self,
        result: Any,
    ) -> None:
        print("------ PROBABILITY ENGINE ------")
        print(
            f"Probabilidad estimada: "
            f"{result.probability:.2f}%"
        )
        print(f"Confianza: {result.confidence}")
        print(
            "Operación aprobada:",
            "SÍ" if result.approved else "NO",
        )
        print(
            f"Recomendación final: "
            f"{result.recommendation}"
        )

        print("Ajustes:")
        for factor, adjustment in result.adjustments.items():
            sign = "+" if adjustment > 0 else ""
            print(f"- {factor}: {sign}{adjustment:.2f}%")

        if result.positive_factors:
            print("Factores positivos:")
            for factor in result.positive_factors:
                print(f"- {factor}")

        if result.negative_factors:
            print("Factores negativos:")
            for factor in result.negative_factors:
                print(f"- {factor}")

    def _validate_context(
        self,
        context: dict[str, Any],
    ) -> None:
        for key in self.REQUIRED_KEYS:
            if key not in context:
                raise KeyError(
                    f"ReportingStage requiere '{key}'."
                )

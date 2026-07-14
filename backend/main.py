from backend.core import ArmsCore
from backend.market import MarketData
from backend.risk import RiskManager
from backend.trend_analyzer import TrendAnalyzer
from backend.connectors.market_connector import MarketConnector
from backend.connectors.data_feed import DataFeed
from backend.indicators.ema_engine import EMAEngine
from backend.indicators.rsi_engine import RSIEngine
from backend.indicators.atr_engine import ATREngine
from backend.strategy.decision_engine import DecisionEngine
from backend.services.data_collector import DataCollector
from backend.services.candle_manager import CandleManager
from backend.intelligence.trading_intelligence import TradingIntelligence
from backend.intelligence.reasoning_engine import ReasoningEngine
from backend.intelligence.confluence_engine import ConfluenceEngine
from backend.risk_management.dynamic_risk_engine import DynamicRiskEngine
from backend.risk_management.trade_levels import TradeLevels
from backend.risk_management.trade_validator import TradeValidator
from backend.models.trade_plan import TradePlan
from backend.services.trade_logger import TradeLogger
from backend.services.plan_history_analyzer import PlanHistoryAnalyzer
from backend.services.execution_simulator import ExecutionSimulator
from backend.services.simulated_trade_logger import SimulatedTradeLogger
from backend.services.trade_plan_factory import TradePlanFactory
from backend.smart_money.market_structure import MarketStructureEngine
from backend.smart_money.bos_engine import BOSEngine
from backend.smart_money.choch_engine import CHoCHEngine
from backend.smart_money.liquidity_engine import LiquidityEngine
from backend.intelligence.probability_engine import ProbabilityEngine
from backend.intelligence.decision_council import DecisionCouncil
from backend.pipeline.arms_pipeline import ArmsPipeline
from backend.pipeline.market_stage import MarketStage
from backend.pipeline.indicator_stage import IndicatorStage
from backend.pipeline.smart_money_stage import SmartMoneyStage


def main():
    # ==============================
    # INICIO
    # ==============================
    arms = ArmsCore()
    arms.start()

    connector = MarketConnector()
    connector.connect()

    # ==============================
    # PIPELINE: DATOS DEL MERCADO
    # ==============================
    collector = DataCollector(provider="SIMULATED")

    pipeline = ArmsPipeline(
        stages=[
            MarketStage(
                collector=collector,
                symbol="NASDAQ / NQ",
                timeframe="1m",
                candle_limit=100,
                max_candles=500,
            ),
            IndicatorStage(
                ema_period=50,
                rsi_period=14,
                atr_period=14,
            ),
            SmartMoneyStage(
                liquidity_tolerance=1.0,
            ),
        ]
    )

    pipeline_context = pipeline.run()

    candles = pipeline_context["candles"]
    candle_manager = pipeline_context["candle_manager"]
    latest_candle = pipeline_context["latest_candle"]
    current_price = pipeline_context["current_price"]
    current_volume = pipeline_context["current_volume"]
    market = pipeline_context["market"]
    feed = pipeline_context["feed"]

    close_prices = pipeline_context["close_prices"]
    ema = pipeline_context["ema"]
    rsi = pipeline_context["rsi"]
    atr = pipeline_context["atr"]

    market_structure = pipeline_context["market_structure"]
    bos = pipeline_context["bos"]
    choch = pipeline_context["choch"]
    liquidity = pipeline_context["liquidity"]

    candle_manager.show_status()
    latest_candle.show()
    feed.show()

    # ==============================
    # RIESGO BASE
    # ==============================
    risk = RiskManager(
        account_balance=17000,
        risk_percent=0.5,
    )
    risk.show_risk()

    # ==============================
    # INDICADORES DESDE PIPELINE
    # ==============================
    ema.show()
    rsi.show()
    atr.show()

    # ==============================
    # SMART MONEY DESDE PIPELINE
    # ==============================
    market_structure.show()
    bos.show()
    choch.show()
    liquidity.show()

    # ==============================
    # TENDENCIA E INTELIGENCIA
    # ==============================
    trend = TrendAnalyzer()
    trend.analyze(
        current_price=current_price,
        ema50=ema.ema,
    )
    trend.show()

    intelligence = TradingIntelligence()
    intelligence.analyze(
        trend=trend.trend,
        current_price=current_price,
        ema=ema.ema,
        rsi=rsi.rsi,
        rsi_status=rsi.status,
        atr=atr.atr,
        atr_status=atr.status,
        market_structure=market_structure.structure,
        bos_detected=bos.bos,
        bos_direction=bos.direction,
        choch_detected=choch.choch,
        choch_direction=choch.direction,
    )
    intelligence.show()

    decision = DecisionEngine()
    decision.analyze(
        intelligence_recommendation=intelligence.recommendation
    )
    decision.show()

    # ==============================
    # RIESGO DINÁMICO Y NIVELES
    # ==============================
    dynamic_risk = DynamicRiskEngine(
        account_balance=17000,
        risk_percent=0.5,
        stop_atr_multiplier=1.5,
        reward_risk_ratio=2.0,
    )

    dynamic_risk.calculate(
        atr=atr.atr,
        point_value=2.0,
    )
    dynamic_risk.show()

    trade_levels = TradeLevels()
    trade_levels.calculate(
        direction=decision.decision,
        entry_price=current_price,
        stop_distance=dynamic_risk.stop_distance,
        take_profit_distance=dynamic_risk.take_profit_distance,
    )
    trade_levels.show()

    # ==============================
    # VALIDACIÓN
    # ==============================
    validator = TradeValidator()
    validator.validate(
        decision=decision.decision,
        confidence=intelligence.confidence,
        contracts=dynamic_risk.contracts,
        rsi_status=rsi.status,
        atr_status=atr.status,
    )
    validator.show()

    # ==============================
    # CONFLUENCE ENGINE
    # ==============================
    confluence = ConfluenceEngine()

    ema_direction = (
        "ALCISTA"
        if current_price > ema.ema
        else "BAJISTA"
        if current_price < ema.ema
        else "NEUTRAL"
    )

    liquidity_data = {
        "sweep_detected": liquidity.sweep_detected,
        "direction": liquidity.sweep_direction,
    }

    atr_data = {
        "value": atr.atr,
        "status": atr.status,
    }

    risk_data = {
        "approved": validator.is_valid,
    }

    confluence_result = confluence.evaluate(
        trend=trend.trend,
        ema=ema_direction,
        rsi=rsi.rsi,
        atr=atr_data,
        structure=market_structure.structure,
        bos=bos.direction if bos.bos else "NEUTRAL",
        choch=choch.direction if choch.choch else "NEUTRAL",
        liquidity=liquidity_data,
        risk=risk_data,
    )

    print("------ CONFLUENCE ENGINE ------")
    print(f"Dirección: {confluence_result.direction}")
    print(f"Puntuación: {confluence_result.score:.2f}/100")
    print(f"Calidad: {confluence_result.grade}")
    print(
        "Operación aprobada:",
        "SÍ" if confluence_result.approved else "NO",
    )
    print(f"Acción final: {confluence_result.action}")

    print("Desglose:")
    for component, points in confluence_result.breakdown.items():
        print(f"- {component}: {points:.2f}")

    if confluence_result.confirmations:
        print("Confirmaciones:")
        for confirmation in confluence_result.confirmations:
            print(f"- {confirmation}")

    if confluence_result.warnings:
        print("Advertencias:")
        for warning in confluence_result.warnings:
            print(f"- {warning}")

    final_authorized = (
        validator.is_valid
        and confluence_result.approved
    )

    final_reasons = list(validator.reasons)

    if not confluence_result.approved:
        final_reasons.extend(confluence_result.warnings)

    

    # ==============================
    # REASONING ENGINE
    # ==============================
    reasoning = ReasoningEngine()

    liquidity_confirmed = (
        liquidity.sweep_detected is True
        or str(liquidity.sweep_detected).upper() == "SÍ"
    )

    reasoning_result = reasoning.evaluate(
        trend=trend.trend,
        market_structure=market_structure.structure,
        bos_direction=(
            bos.direction
            if str(bos.bos).upper() == "SÍ"
            else "NINGUNA"
        ),
        choch_direction=(
            choch.direction
            if str(choch.choch).upper() == "SÍ"
            else "NINGUNA"
        ),
        liquidity_confirmed=liquidity_confirmed,
        rsi_status=rsi.status,
        atr_status=atr.status,
        reward_risk_ratio=2.0,
        risk_allowed=validator.is_valid,
        session_allowed=True,
    )

    reasoning_result.show()

    # ==============================
    # PROBABILITY ENGINE
    # ==============================
    probability_engine = ProbabilityEngine()

    probability_result = probability_engine.evaluate(
        confluence=confluence_result,
    )

    print("------ PROBABILITY ENGINE ------")
    print(
        f"Probabilidad estimada: "
        f"{probability_result.probability:.2f}%"
    )
    print(f"Confianza: {probability_result.confidence}")
    print(
        "Operación aprobada:",
        "SÍ" if probability_result.approved else "NO",
    )
    print(
        f"Recomendación final: "
        f"{probability_result.recommendation}"
    )

    print("Ajustes:")
    for factor, adjustment in probability_result.adjustments.items():
        sign = "+" if adjustment > 0 else ""
        print(f"- {factor}: {sign}{adjustment:.2f}%")

    if probability_result.positive_factors:
        print("Factores positivos:")
        for factor in probability_result.positive_factors:
            print(f"- {factor}")

    if probability_result.negative_factors:
        print("Factores negativos:")
        for factor in probability_result.negative_factors:
            print(f"- {factor}")

    final_authorized = (
        final_authorized
        and probability_result.approved
    )

    if not probability_result.approved:
        final_reasons.extend(
            probability_result.negative_factors
        )

    # ==============================
    # DECISION COUNCIL
    # ==============================
    council = DecisionCouncil()

    council_result = council.evaluate(
        confluence=confluence_result,
        probability=probability_result,
        reasoning=reasoning_result,
        risk_allowed=validator.is_valid,
        session_allowed=True,
    )

    council_result.show()

    # ==============================
    # PLAN DE OPERACIÓN
    # ==============================
    trade_plan_factory = TradePlanFactory()

    trade_plan = trade_plan_factory.create(
        symbol=latest_candle.symbol,
        timeframe=latest_candle.timeframe,
        council_result=council_result,
        entry_price=trade_levels.entry_price,
        stop_loss=trade_levels.stop_loss,
        take_profit=trade_levels.take_profit,
        contracts=dynamic_risk.contracts,
        risk_amount=dynamic_risk.risk_amount,
    )

    trade_plan.show()

    # ==============================
    # REGISTRO DEL PLAN
    # ==============================
    logger = TradeLogger(
        file_path="data/trade_plans.jsonl"
    )
    logger.save(trade_plan)
    logger.show_confirmation()

    history_analyzer = PlanHistoryAnalyzer(
        file_path="data/trade_plans.jsonl"
    )
    history_analyzer.analyze()
    history_analyzer.show()

    # ==============================
    # SIMULACIÓN DE EJECUCIÓN
    # ==============================
    simulator = ExecutionSimulator(
        point_value=2.0
    )

    next_candle = collector.get_latest_candle(
        symbol=latest_candle.symbol,
        timeframe=latest_candle.timeframe,
    )

    simulated_trade = simulator.execute(
        trade_plan=trade_plan,
        next_candle=next_candle,
    )

    if simulated_trade is not None:
        simulated_trade.show()

        simulated_trade_logger = SimulatedTradeLogger(
            file_path="data/simulated_trades.jsonl"
        )

        simulated_trade_logger.save(simulated_trade)
        simulated_trade_logger.show_confirmation()


if __name__ == "__main__":
    main()
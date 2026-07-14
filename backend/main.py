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
from backend.pipeline.intelligence_stage import IntelligenceStage
from backend.pipeline.risk_stage import RiskStage
from backend.pipeline.decision_stage import DecisionStage
from backend.pipeline.trade_plan_stage import TradePlanStage


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
            IntelligenceStage(),
            RiskStage(
                account_balance=17000,
                risk_percent=0.5,
                stop_atr_multiplier=1.5,
                reward_risk_ratio=2.0,
                point_value=2.0,
            ),
            DecisionStage(
                reward_risk_ratio=2.0,
            ),
            TradePlanStage(),
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

    trend = pipeline_context["trend"]
    intelligence = pipeline_context["intelligence"]
    decision = pipeline_context["decision"]

    risk = pipeline_context["risk_manager"]
    dynamic_risk = pipeline_context["dynamic_risk"]
    trade_levels = pipeline_context["trade_levels"]
    validator = pipeline_context["validator"]

    confluence_result = pipeline_context["confluence_result"]
    reasoning_result = pipeline_context["reasoning_result"]
    probability_result = pipeline_context["probability_result"]
    council_result = pipeline_context["council_result"]
    trade_plan = pipeline_context["trade_plan"]

    candle_manager.show_status()
    latest_candle.show()
    feed.show()

    # ==============================
    # RIESGO BASE DESDE PIPELINE
    # ==============================
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
    # INTELIGENCIA DESDE PIPELINE
    # ==============================
    trend.show()
    intelligence.show()
    decision.show()

    # ==============================
    # RIESGO Y VALIDACIÓN DESDE PIPELINE
    # ==============================
    dynamic_risk.show()
    trade_levels.show()
    validator.show()

    # ==============================
    # DECISIÓN DESDE PIPELINE
    # ==============================
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

    reasoning_result.show()

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

    council_result.show()

    # ==============================
    # PLAN DE OPERACIÓN DESDE PIPELINE
    # ==============================
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
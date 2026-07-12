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
from backend.risk_management.dynamic_risk_engine import DynamicRiskEngine
from backend.risk_management.trade_levels import TradeLevels
from backend.risk_management.trade_validator import TradeValidator
from backend.models.trade_plan import TradePlan
from backend.services.trade_logger import TradeLogger
from backend.services.plan_history_analyzer import PlanHistoryAnalyzer
from backend.services.execution_simulator import ExecutionSimulator
from backend.services.simulated_trade_logger import SimulatedTradeLogger
from backend.smart_money.market_structure import MarketStructureEngine
from backend.smart_money.bos_engine import BOSEngine
from backend.smart_money.choch_engine import CHoCHEngine


def main():
    # ==============================
    # INICIO
    # ==============================
    arms = ArmsCore()
    arms.start()

    connector = MarketConnector()
    connector.connect()

    # ==============================
    # DATOS DEL MERCADO
    # ==============================
    collector = DataCollector(provider="SIMULATED")

    candles = collector.get_historical_candles(
        symbol="NASDAQ / NQ",
        timeframe="1m",
        limit=100,
    )

    candle_manager = CandleManager(max_candles=500)

    for candle in candles:
        candle_manager.add_candle(candle)

    candle_manager.show_status()

    latest_candle = candle_manager.get_latest_candle()

    if latest_candle is None:
        raise RuntimeError("No hay velas disponibles para analizar.")

    latest_candle.show()

    current_price = latest_candle.close
    current_volume = latest_candle.volume

    market = MarketData(symbol=latest_candle.symbol)
    market.update_price(current_price)

    feed = DataFeed(symbol=latest_candle.symbol)
    feed.update(
        price=current_price,
        volume=current_volume,
        timeframe=latest_candle.timeframe,
    )
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
    # INDICADORES
    # ==============================
    close_prices = candle_manager.get_close_prices()

    ema = EMAEngine(period=50)
    ema.calculate(close_prices)
    ema.show()

    rsi = RSIEngine(period=14)
    rsi.calculate(close_prices)
    rsi.show()

    atr = ATREngine(period=14)
    atr.calculate(candles)
    atr.show()

    # ==============================
    # SMART MONEY
    # ==============================
        # ==============================
    # SMART MONEY
    # ==============================
    market_structure = MarketStructureEngine()
    market_structure.analyze(candles)
    market_structure.show()

    bos = BOSEngine()
    bos.analyze(candles)
    bos.show()

    choch = CHoCHEngine()
    choch.analyze(
        candles=candles,
        market_structure=market_structure.structure,
    )
    choch.show()
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
    # PLAN DE OPERACIÓN
    # ==============================
    trade_plan = TradePlan(
        symbol=latest_candle.symbol,
        timeframe=latest_candle.timeframe,
        decision=decision.decision,
        confidence=intelligence.confidence,
        entry_price=trade_levels.entry_price,
        stop_loss=trade_levels.stop_loss,
        take_profit=trade_levels.take_profit,
        contracts=dynamic_risk.contracts,
        risk_amount=dynamic_risk.risk_amount,
        authorized=validator.is_valid,
        reasons=validator.reasons,
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
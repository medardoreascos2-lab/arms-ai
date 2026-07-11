from backend.core import ArmsCore
from backend.market import MarketData
from backend.risk import RiskManager
from backend.trend_analyzer import TrendAnalyzer
from backend.connectors.market_connector import MarketConnector
from backend.connectors.data_feed import DataFeed
from backend.indicators.ema_engine import EMAEngine
from backend.strategy.decision_engine import DecisionEngine
from backend.services.data_collector import DataCollector
from backend.services.candle_manager import CandleManager
from backend.indicators.rsi_engine import RSIEngine
from backend.indicators.atr_engine import ATREngine
from backend.intelligence.trading_intelligence import TradingIntelligence

def main():
    arms = ArmsCore()
    arms.start()

    connector = MarketConnector()
    connector.connect()

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

    risk = RiskManager(
        account_balance=17000,
        risk_percent=0.5,
    )
    risk.show_risk()

    atr = ATREngine(period=14)
    atr.calculate(candles)
    atr.show()

    feed = DataFeed(symbol=latest_candle.symbol)
    feed.update(
        price=current_price,
        volume=current_volume,
        timeframe=latest_candle.timeframe,
    )
    feed.show()

    close_prices = candle_manager.get_close_prices()

    ema = EMAEngine(period=50)
    ema.calculate(close_prices)
    ema.show()

    rsi = RSIEngine(period=14)
    rsi.calculate(close_prices)
    rsi.show()

    trend = TrendAnalyzer()
    trend.analyze(
        current_price=current_price,
        ema50=ema.ema,
    )
    trend.show()

    decision = DecisionEngine()
    decision.analyze(
        trend=trend.trend,
        price=current_price,
        ema=ema.ema,
    )
    decision.show()

    intelligence = TradingIntelligence()

    intelligence.analyze(
        trend=trend.trend,
        current_price=current_price,
        ema=ema.ema,
        rsi=rsi.rsi,
        rsi_status=rsi.status,
        atr=atr.atr,
        atr_status=atr.status,
    )

    intelligence.show()


if __name__ == "__main__":
    main()
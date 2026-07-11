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


def main():
    # ==============================
    # INICIO DEL SISTEMA
    # ==============================
    arms = ArmsCore()
    arms.start()

    # ==============================
    # CONEXIÓN AL MERCADO
    # ==============================
    connector = MarketConnector()
    connector.connect()

    # ==============================
    # OBTENER ÚLTIMA VELA
    # ==============================
    collector = DataCollector(provider="SIMULATED")

    candle = collector.get_latest_candle(
        symbol="NASDAQ / NQ",
        timeframe="1m",
    )

    candle.show()

    # ==============================
    # CANDLE MANAGER
    # ==============================
    candle_manager = CandleManager(max_candles=500)
    candle_manager.add_candle(candle)
    candle_manager.show_status()

    # Datos principales
    current_price = candle.close
    current_volume = candle.volume

    # ==============================
    # MARKET DATA
    # ==============================
    market = MarketData(symbol=candle.symbol)
    market.update_price(current_price)

    # ==============================
    # RISK MANAGER
    # ==============================
    risk = RiskManager(
        account_balance=17000,
        risk_percent=0.5,
    )
    risk.show_risk()

    # ==============================
    # DATA FEED
    # ==============================
    feed = DataFeed(symbol=candle.symbol)

    feed.update(
        price=current_price,
        volume=current_volume,
        timeframe=candle.timeframe,
    )

    feed.show()

    # ==============================
    # EMA ENGINE
    # ==============================
    ema = EMAEngine(period=50)

    prices = [
        23500,
        23505,
        23512,
        23520,
        23528,
        23535,
        23541,
        23548,
        23552,
        23560,
    ] * 5

    ema.calculate(prices)
    ema.show()

    # ==============================
    # TREND ANALYZER
    # ==============================
    trend = TrendAnalyzer()

    trend.analyze(
        current_price=current_price,
        ema50=ema.ema,
    )

    trend.show()

    # ==============================
    # DECISION ENGINE
    # ==============================
    decision = DecisionEngine()

    decision.analyze(
        trend=trend.trend,
        price=current_price,
        ema=ema.ema,
    )

    decision.show()


if __name__ == "__main__":
    main()
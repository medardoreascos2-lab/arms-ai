from backend.core import ArmsCore
from backend.market import MarketData
from backend.risk import RiskManager
from backend.trend_analyzer import TrendAnalyzer
from backend.connectors.market_connector import MarketConnector
from backend.connectors.data_feed import DataFeed
from backend.indicators.ema_engine import EMAEngine
from backend.strategy.decision_engine import DecisionEngine


def main():
    arms = ArmsCore()
    arms.start()

    market = MarketData(symbol="NASDAQ / NQ")
    market.update_price(21500.25)

    risk = RiskManager(account_balance=17000, risk_percent=0.5)
    risk.show_risk()

    connector = MarketConnector()
    connector.connect()

    feed = DataFeed(symbol="NASDAQ / NQ")
    feed.update(price=21500.25, volume=1250, timeframe="1m")
    feed.show()

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

    trend = TrendAnalyzer()
    trend.analyze(
        current_price=21500.25,
        ema50=ema.ema,
    )
    trend.show()

    decision = DecisionEngine()
    decision.analyze(
        trend=trend.trend,
        price=21500.25,
        ema=ema.ema,
    )
    decision.show()


if __name__ == "__main__":
    main()
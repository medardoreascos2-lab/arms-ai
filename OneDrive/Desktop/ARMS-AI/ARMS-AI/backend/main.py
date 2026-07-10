from core import ArmsCore
from market import MarketData
from risk import RiskManager
from connectors.market_connector import MarketConnector
from backend.data_feed import DataFeed
from backend.trend_analyzer import TrendAnalyzer

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
trend = TrendAnalyzer()

trend.analyze(
    current_price=21500.25,
    ema50=21480.00
)

trend.show()

if __name__ == "__main__":
    main()
    
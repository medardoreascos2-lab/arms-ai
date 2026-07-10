from core import ArmsCore
from market import MarketData
from risk import RiskManager

def main():
    arms = ArmsCore()
    arms.start()

    market = MarketData(symbol="NASDAQ / NQ")
    market.update_price(21500.25)

    risk = RiskManager(account_balance=17000, risk_percent=0.5)
    risk.show_risk()

if __name__ == "__main__":
    main()
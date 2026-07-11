class MarketData:
    def __init__(self, symbol="NQ"):
        self.symbol = symbol
        self.price = None

    def update_price(self, price):
        self.price = price
        print(f"Precio actualizado para {self.symbol}: {self.price}")

    def get_price(self):
        return self.price
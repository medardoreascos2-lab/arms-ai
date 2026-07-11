class DataFeed:
    def __init__(self, symbol="NQ"):
        self.symbol = symbol
        self.last_price = None
        self.volume = None
        self.timeframe = "1m"

    def update(self, price, volume, timeframe="1m"):
        self.last_price = price
        self.volume = volume
        self.timeframe = timeframe

    def show(self):
        print("----- DATA FEED -----")
        print(f"Símbolo: {self.symbol}")
        print(f"Precio: {self.last_price}")
        print(f"Volumen: {self.volume}")
        print(f"Timeframe: {self.timeframe}")
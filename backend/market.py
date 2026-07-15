class MarketData:
    def __init__(
        self,
        symbol: str = "NQ",
        verbose: bool = True,
    ) -> None:
        self.symbol = symbol
        self.price = None
        self.verbose = verbose

    def update_price(
        self,
        price: float,
    ) -> None:
        self.price = price

        if self.verbose:
            print(
                f"Precio actualizado para "
                f"{self.symbol}: {self.price}"
            )

    def get_price(self):
        return self.price

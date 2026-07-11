class TradeLevels:
    def __init__(self):
        self.entry_price: float | None = None
        self.stop_loss: float | None = None
        self.take_profit: float | None = None
        self.direction = "ESPERAR"

    def calculate(
        self,
        direction: str,
        entry_price: float,
        stop_distance: float,
        take_profit_distance: float,
    ) -> dict:
        if entry_price <= 0:
            raise ValueError("El precio de entrada debe ser mayor que cero.")

        if stop_distance <= 0:
            raise ValueError("La distancia del stop debe ser mayor que cero.")

        if take_profit_distance <= 0:
            raise ValueError(
                "La distancia del take profit debe ser mayor que cero."
            )

        self.direction = direction
        self.entry_price = entry_price

        if direction == "BUSCAR COMPRAS":
            self.stop_loss = entry_price - stop_distance
            self.take_profit = entry_price + take_profit_distance

        elif direction == "BUSCAR VENTAS":
            self.stop_loss = entry_price + stop_distance
            self.take_profit = entry_price - take_profit_distance

        else:
            self.stop_loss = None
            self.take_profit = None

        return {
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
        }

    def show(self) -> None:
        print("------ TRADE LEVELS ------")
        print(f"Dirección: {self.direction}")

        if self.direction == "ESPERAR":
            print("No se generan niveles de operación.")
            return

        print(f"Entrada: {self.entry_price:.2f}")
        print(f"Stop Loss: {self.stop_loss:.2f}")
        print(f"Take Profit: {self.take_profit:.2f}")
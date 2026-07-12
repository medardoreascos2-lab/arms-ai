from backend.models.candle import Candle


class MarketStructureEngine:
    def __init__(self):
        self.structure = "LATERAL"
        self.last_high_type = "SIN DATOS"
        self.last_low_type = "SIN DATOS"

    def analyze(self, candles: list[Candle]) -> str:
        if len(candles) < 3:
            raise ValueError(
                "Se necesitan al menos 3 velas para analizar la estructura."
            )

        previous = candles[-3]
        middle = candles[-2]
        current = candles[-1]

        # Clasificación de máximos
        if current.high > middle.high:
            self.last_high_type = "HH"
        elif current.high < middle.high:
            self.last_high_type = "LH"
        else:
            self.last_high_type = "EH"

        # Clasificación de mínimos
        if current.low > middle.low:
            self.last_low_type = "HL"
        elif current.low < middle.low:
            self.last_low_type = "LL"
        else:
            self.last_low_type = "EL"

        # Estructura general
        if self.last_high_type == "HH" and self.last_low_type == "HL":
            self.structure = "ALCISTA"

        elif self.last_high_type == "LH" and self.last_low_type == "LL":
            self.structure = "BAJISTA"

        else:
            self.structure = "LATERAL"

        return self.structure

    def show(self) -> None:
        print("------ MARKET STRUCTURE ------")
        print(f"Último máximo: {self.last_high_type}")
        print(f"Último mínimo: {self.last_low_type}")
        print(f"Estructura: {self.structure}")
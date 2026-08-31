import math


class DynamicRiskEngine:

    def __init__(
        self,
        account_balance: float,
        risk_percent: float = 0.5,
        stop_atr_multiplier: float = 1.5,
        reward_risk_ratio: float = 2.0,
        instrument: str = "MNQ",
        point_value: float | None = None,
    ):

        if account_balance <= 0:
            raise ValueError(
                "El balance debe ser mayor que cero."
            )

        if risk_percent <= 0:
            raise ValueError(
                "El porcentaje de riesgo debe ser mayor que cero."
            )

        instrument = instrument.upper()

        if not instrument:
            raise ValueError(
                "El instrumento no puede estar vacío."
            )

        if point_value is None or point_value <= 0:
            raise ValueError(
                "El point_value debe ser mayor que cero."
            )

        self.account_balance = account_balance
        self.risk_percent = risk_percent
        self.stop_atr_multiplier = stop_atr_multiplier
        self.reward_risk_ratio = reward_risk_ratio

        self.instrument = instrument
        self.point_value = point_value

        self.risk_amount = 0.0
        self.stop_distance = 0.0
        self.take_profit_distance = 0.0
        self.risk_per_contract = 0.0
        self.contracts = 0


    def calculate(
        self,
        atr: float,
    ) -> dict:

        if atr <= 0:
            raise ValueError(
                "El ATR debe ser mayor que cero."
            )


        self.risk_amount = (
            self.account_balance
            * self.risk_percent
            / 100
        )


        self.stop_distance = (
            atr
            * self.stop_atr_multiplier
        )


        self.risk_per_contract = (
            self.stop_distance
            * self.point_value
        )


        self.contracts = math.floor(
            self.risk_amount
            / self.risk_per_contract
        )


        self.take_profit_distance = (
            self.stop_distance
            * self.reward_risk_ratio
        )


        return {
            "instrument": self.instrument,
            "risk_amount": self.risk_amount,
            "stop_distance": self.stop_distance,
            "take_profit_distance": self.take_profit_distance,
            "risk_per_contract": self.risk_per_contract,
            "contracts": self.contracts,
        }


    def show(self) -> None:

        print(
            "------ DYNAMIC RISK ENGINE ------"
        )

        print(
            f"Instrumento: {self.instrument}"
        )

        print(
            f"Valor punto: ${self.point_value}"
        )

        print(
            f"Riesgo máximo: ${self.risk_amount:.2f}"
        )

        print(
            f"Riesgo contrato: ${self.risk_per_contract:.2f}"
        )

        print(
            f"Stop: {self.stop_distance:.2f} puntos"
        )

        print(
            f"Take Profit: "
            f"{self.take_profit_distance:.2f} puntos"
        )

        print(
            f"Contratos permitidos: {self.contracts}"
        )

        if self.contracts < 1:
            print(
                "Operación rechazada: "
                "riesgo insuficiente."
            )

import math


class DynamicRiskEngine:
    def __init__(
        self,
        account_balance: float,
        risk_percent: float = 0.5,
        stop_atr_multiplier: float = 1.5,
        reward_risk_ratio: float = 2.0,
    ):
        if account_balance <= 0:
            raise ValueError("El balance debe ser mayor que cero.")

        if risk_percent <= 0:
            raise ValueError("El porcentaje de riesgo debe ser mayor que cero.")

        self.account_balance = account_balance
        self.risk_percent = risk_percent
        self.stop_atr_multiplier = stop_atr_multiplier
        self.reward_risk_ratio = reward_risk_ratio

        self.risk_amount = 0.0
        self.stop_distance = 0.0
        self.take_profit_distance = 0.0
        self.contracts = 0

    def calculate(
        self,
        atr: float,
        point_value: float,
    ) -> dict:
        if atr <= 0:
            raise ValueError("El ATR debe ser mayor que cero.")

        if point_value <= 0:
            raise ValueError("El valor por punto debe ser mayor que cero.")

        self.risk_amount = (
            self.account_balance * self.risk_percent / 100
        )

        self.stop_distance = atr * self.stop_atr_multiplier

        risk_per_contract = self.stop_distance * point_value

        self.contracts = math.floor(
            self.risk_amount / risk_per_contract
        )

        self.take_profit_distance = (
            self.stop_distance * self.reward_risk_ratio
        )

        return {
            "risk_amount": self.risk_amount,
            "stop_distance": self.stop_distance,
            "take_profit_distance": self.take_profit_distance,
            "contracts": self.contracts,
        }

    def show(self) -> None:
        print("------ DYNAMIC RISK ENGINE ------")
        print(f"Riesgo máximo: ${self.risk_amount:.2f}")
        print(f"Distancia del stop: {self.stop_distance:.2f} puntos")
        print(
            f"Distancia del take profit: "
            f"{self.take_profit_distance:.2f} puntos"
        )
        print(f"Contratos permitidos: {self.contracts}")

        if self.contracts < 1:
            print(
                "Operación rechazada: el riesgo disponible "
                "no permite abrir un contrato."
            )
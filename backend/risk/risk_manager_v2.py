from dataclasses import dataclass


@dataclass
class RiskValidationResult:

    allowed: bool

    risk_amount: float

    reason: str



class RiskManagerV2:
    """
    Gestor profesional de riesgo ARMS AI.

    Controla:

    - Riesgo por operación
    - Pérdida diaria máxima
    - Bloqueo de operaciones
    """


    def __init__(
        self,
        *,
        account_balance: float = 150000,
        risk_percent: float = 0.5,
        daily_loss_limit: float = 3000,
    ):

        self.account_balance = (
            account_balance
        )

        self.risk_percent = (
            risk_percent
        )

        self.daily_loss_limit = (
            daily_loss_limit
        )

        self.daily_loss = 0.0



    def calculate_risk_amount(
        self,
    ):

        return (
            self.account_balance
            *
            (
                self.risk_percent / 100
            )
        )



    def validate_trade(
        self,
        *,
        current_loss: float = 0.0,
    ) -> RiskValidationResult:


        risk_amount = (
            self.calculate_risk_amount()
        )


        if (
            current_loss
            >=
            self.daily_loss_limit
        ):

            return RiskValidationResult(

                allowed=False,

                risk_amount=risk_amount,

                reason=(
                    "DAILY LOSS LIMIT REACHED"
                ),
            )


        return RiskValidationResult(

            allowed=True,

            risk_amount=risk_amount,

            reason=(
                "RISK APPROVED"
            ),
        )

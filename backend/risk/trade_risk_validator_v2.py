from backend.risk.multi_account_risk_engine_v2 import (
    MultiAccountRiskEngineV2,
)


class TradeRiskValidatorV2:
    """
    Validador de riesgo antes de ejecutar operaciones.
    """

    def __init__(
        self,
    ):

        self.risk_engine = (
            MultiAccountRiskEngineV2()
        )



    def validate_trade(
        self,
        contracts: int,
        risk_amount: float,
    ):

        profile = (
            self.risk_engine
            .get_active_risk_profile()
        )


        max_risk = (
            profile["risk_per_trade"]
        )


        max_contracts = (
            profile["max_contracts"]
        )



        if contracts > max_contracts:

            return {

                "status": "BLOCKED",

                "reason":
                    "MAX_CONTRACTS_EXCEEDED",

                "allowed_contracts":
                    max_contracts,

            }



        if risk_amount > max_risk:

            return {

                "status": "BLOCKED",

                "reason":
                    "RISK_LIMIT_EXCEEDED",

                "allowed_risk":
                    max_risk,

            }



        return {

            "status": "APPROVED",

            "account":
                profile["account"],

            "account_size":
                profile["account_size"],

            "risk_used":
                risk_amount,

            "contracts":
                contracts,

        }

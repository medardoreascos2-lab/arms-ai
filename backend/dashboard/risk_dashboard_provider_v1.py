from backend.risk.account_config_manager_v1 import (
    AccountConfigManagerV1,
)


class RiskDashboardProviderV1:
    """
    Proveedor de información de riesgo
    para Dashboard ARMS AI.
    """


    def __init__(
        self,
    ):

        self.account_manager = (
            AccountConfigManagerV1()
        )



    def get_risk_status(
        self,
    ):


        profile = (
            self.account_manager
            .get_profile()
        )


        risk_amount = (
            profile.account_balance
            *
            (
                profile.risk_percent / 100
            )
        )


        return {

            "account": profile.name,

            "balance": (
                profile.account_balance
            ),

            "risk_percent": (
                profile.risk_percent
            ),

            "risk_per_trade": (
                risk_amount
            ),

            "daily_loss_limit": (
                profile.daily_loss_limit
            ),

            "max_drawdown": (
                profile.max_drawdown
            ),

            "status": (
                "TRADING ENABLED"
            ),
        }

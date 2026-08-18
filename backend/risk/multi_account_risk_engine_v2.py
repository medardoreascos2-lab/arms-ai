from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)


class MultiAccountRiskEngineV2:
    """
    Motor de riesgo multi-cuenta ARMS AI.
    """

    def __init__(
        self,
        account_manager=None,
    ):

        self.account_manager = (
            account_manager
            if account_manager is not None
            else AccountConfigManagerV2()
        )


    def get_active_risk_profile(
        self,
    ):

        account = (
            self.account_manager
            .get_active_account()
        )

        risk_per_trade = (
            account.account_size
            * account.risk_percent
            / 100
        )

        return {
            "account":
                self.account_manager
                .get_active_account_name(),

            "firm":
                account.firm_name,

            "account_stage":
                account.account_stage,

            "account_size":
                account.account_size,

            "risk_percent":
                account.risk_percent,

            "risk_per_trade":
                risk_per_trade,

            # Legacy fallback.
            "max_contracts":
                account.max_contracts,

            "max_mini_contracts":
                account.max_mini_contracts,

            "max_micro_contracts":
                account.max_micro_contracts,

            "daily_loss_limit":
                account.daily_loss_limit,

            "maximum_loss_limit":
                account.maximum_loss_limit,

            "max_drawdown":
                account.max_drawdown,

            "platform":
                account.platform,

            "news_allowed":
                account.news_allowed,
        }

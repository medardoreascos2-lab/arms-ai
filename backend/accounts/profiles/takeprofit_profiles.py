from backend.accounts.funding_firm_profile_v1 import (
    FundingFirmProfile,
)


class TakeProfitTraderProfiles:


    @staticmethod
    def account_50k():

        return FundingFirmProfile(

            firm_name="TAKE_PROFIT_TRADER",

            account_size=50000,

            profit_target=3000,

            daily_loss_limit=1100,

            max_drawdown=2000,

            max_contracts=6,

            risk_percent=0.5,

            platform="TRADOVATE",

            drawdown_type="TRAILING",

            news_allowed=False,

            account_stage="EVALUATION",

            max_mini_contracts=6,
            max_micro_contracts=60,

            maximum_loss_limit=2000.0,
        )



    @staticmethod
    def account_150k():

        return FundingFirmProfile(

            firm_name="TAKE_PROFIT_TRADER",

            account_size=150000,

            profit_target=9000,

            daily_loss_limit=3000,

            max_drawdown=4500,

            max_contracts=15,

            risk_percent=0.5,

            platform="TRADOVATE",

            drawdown_type="TRAILING",

            news_allowed=False,

            account_stage="EVALUATION",

            max_mini_contracts=15,
            max_micro_contracts=150,

            maximum_loss_limit=4500.0,
        )

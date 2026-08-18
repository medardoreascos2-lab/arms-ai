from backend.accounts.funding_firm_profile_v1 import (
    FundingFirmProfile,
)


class TopstepProfiles:
    """
    Perfiles Topstep utilizados por ARMS AI.

    Estos perfiles representan Trading Combine.
    """


    @staticmethod
    def account_50k():

        return FundingFirmProfile(
            firm_name="TOPSTEP",
            account_size=50000,
            profit_target=3000.0,

            # No se fuerza como regla universal
            # dentro de este perfil.
            daily_loss_limit=None,

            max_drawdown=2000.0,

            # Compatibilidad con consumidores
            # legacy que todavía esperan este campo.
            max_contracts=5,

            risk_percent=0.5,
            platform="TOPSTEPX",
            drawdown_type="TRAILING",
            news_allowed=True,

            account_stage="TRADING_COMBINE",

            max_mini_contracts=5,
            max_micro_contracts=50,

            maximum_loss_limit=2000.0,
        )


    @staticmethod
    def account_150k():

        return FundingFirmProfile(
            firm_name="TOPSTEP",
            account_size=150000,
            profit_target=9000.0,

            daily_loss_limit=None,

            max_drawdown=4500.0,

            # Compatibilidad legacy.
            max_contracts=15,

            risk_percent=0.5,
            platform="TOPSTEPX",
            drawdown_type="TRAILING",
            news_allowed=True,

            account_stage="TRADING_COMBINE",

            max_mini_contracts=15,
            max_micro_contracts=150,

            maximum_loss_limit=4500.0,
        )

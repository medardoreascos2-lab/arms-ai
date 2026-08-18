from backend.accounts.profiles.takeprofit_profiles import (
    TakeProfitTraderProfiles,
)

from backend.accounts.profiles.topstep_profiles import (
    TopstepProfiles,
)


class AccountRegistryV1:
    """
    Registro central de cuentas ARMS AI.
    """

    def __init__(
        self,
    ):

        self.accounts = {

            "TOPSTEP_50K":
                TopstepProfiles.account_50k(),

            "TOPSTEP_150K":
                TopstepProfiles.account_150k(),

            "TAKE_PROFIT_TRADER_50K":
                TakeProfitTraderProfiles.account_50k(),

            "TAKE_PROFIT_TRADER_150K":
                TakeProfitTraderProfiles.account_150k(),

        }


    def get_account(
        self,
        account_name: str,
    ):

        normalized = (
            str(account_name)
            .strip()
            .upper()
        )

        if normalized not in self.accounts:

            raise ValueError(
                f"Cuenta no registrada: {normalized}"
            )

        return self.accounts[
            normalized
        ]


    def list_accounts(
        self,
    ):

        return list(
            self.accounts.keys()
        )

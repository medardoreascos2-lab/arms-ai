import json
from pathlib import Path

from backend.risk.account_profile_v1 import (
    AccountProfileFactory,
    AccountProfile,
)


class AccountConfigManagerV1:
    """
    Gestiona la cuenta activa de ARMS AI
    desde archivo de configuración.
    """


    def __init__(
        self,
        config_path: str = "backend/config/accounts.json",
    ):

        self.config_path = Path(
            config_path
        )


    def get_active_account_name(
        self,
    ) -> str:


        with open(
            self.config_path,
            "r",
            encoding="utf-8",
        ) as file:

            config = json.load(
                file
            )


        return config.get(
            "active_account",
            "TOPSTEP_150K",
        )



    def get_profile(
        self,
    ) -> AccountProfile:


        account_name = (
            self.get_active_account_name()
        )


        if account_name == "TOPSTEP_50K":

            return (
                AccountProfileFactory
                .topstep_50k()
            )


        if account_name == "TOPSTEP_150K":

            return (
                AccountProfileFactory
                .topstep_150k()
            )


        if account_name == "PERSONAL":

            return (
                AccountProfileFactory
                .personal(
                    balance=10000,
                    risk=1.0,
                )
            )


        raise ValueError(
            f"Cuenta no soportada: {account_name}"
        )

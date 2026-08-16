import json
from pathlib import Path


class AccountSwitcherV1:
    """
    Cambia la cuenta activa de ARMS AI.
    """


    def __init__(
        self,
        config_path: str = "backend/config/accounts.json",
    ):

        self.config_path = Path(
            config_path
        )


    def switch_account(
        self,
        account_name: str,
    ):

        with open(
            self.config_path,
            "r",
            encoding="utf-8",
        ) as file:

            config = json.load(
                file
            )


        config["active_account"] = (
            account_name
        )


        with open(
            self.config_path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                config,
                file,
                indent=4,
            )


        return {
            "status": "ACCOUNT_CHANGED",
            "active_account": account_name,
        }

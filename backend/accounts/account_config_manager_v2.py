import json
from pathlib import Path

from backend.accounts.account_registry_v1 import (
    AccountRegistryV1,
)


class AccountConfigManagerV2:
    """
    Gestor central de configuración
    de cuentas multi-firma ARMS AI.

    La cuenta activa se persiste en el mismo
    accounts.json utilizado por la arquitectura V1.
    """

    DEFAULT_CONFIG_PATH = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "accounts.json"
    )


    def __init__(
        self,
        config_path=None,
        registry=None,
    ):

        self.config_path = Path(
            config_path
            if config_path is not None
            else self.DEFAULT_CONFIG_PATH
        )

        self.registry = (
            registry
            if registry is not None
            else AccountRegistryV1()
        )

        self.active_account = (
            self._load_active_account()
        )


    def _load_active_account(
        self,
    ):

        if not self.config_path.exists():

            raise FileNotFoundError(
                "No existe configuración de cuentas: "
                f"{self.config_path}"
            )

        with self.config_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            config = json.load(
                file
            )

        account_name = (
            config.get(
                "active_account"
            )
        )

        if not isinstance(
            account_name,
            str,
        ) or not account_name.strip():

            raise ValueError(
                "accounts.json no contiene "
                "active_account válido."
            )

        return account_name.strip()


    def _save_active_account(
        self,
        account_name: str,
    ):

        self.config_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.config_path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                {
                    "active_account":
                        account_name,
                },
                file,
                indent=4,
            )

            file.write("\n")


    def set_active_account(
        self,
        account_name: str,
    ):

        account = (
            self.registry
            .get_account(
                account_name
            )
        )

        self._save_active_account(
            account_name
        )

        self.active_account = (
            account_name
        )

        return account


    def get_active_account(
        self,
    ):

        return (
            self.registry
            .get_account(
                self.active_account
            )
        )


    def get_active_account_name(
        self,
    ):

        return self.active_account


    def reload(
        self,
    ):

        self.active_account = (
            self._load_active_account()
        )

        return self.active_account


    def get_available_accounts(
        self,
    ):

        return (
            self.registry
            .list_accounts()
        )

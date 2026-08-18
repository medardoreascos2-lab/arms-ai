from dataclasses import dataclass


@dataclass
class FundingFirmProfile:
    """
    Perfil estándar de cuenta para ARMS AI.

    Los límites MINI y MICRO pertenecen a la
    cuenta/firma, no al instrumento.
    """

    firm_name: str

    account_size: int

    profit_target: float

    daily_loss_limit: float | None

    max_drawdown: float

    max_contracts: int

    risk_percent: float

    platform: str

    drawdown_type: str

    news_allowed: bool

    account_stage: str = "UNKNOWN"

    max_mini_contracts: int | None = None

    max_micro_contracts: int | None = None

    maximum_loss_limit: float | None = None


    def get_contract_limit(
        self,
        contract_class: str,
    ) -> int:

        normalized = (
            str(contract_class)
            .strip()
            .upper()
        )

        if normalized == "MINI":

            if self.max_mini_contracts is not None:

                return int(
                    self.max_mini_contracts
                )

            return int(
                self.max_contracts
            )


        if normalized == "MICRO":

            if self.max_micro_contracts is not None:

                return int(
                    self.max_micro_contracts
                )

            return int(
                self.max_contracts
            )


        raise ValueError(
            "Clase de contrato no soportada: "
            f"{contract_class}"
        )

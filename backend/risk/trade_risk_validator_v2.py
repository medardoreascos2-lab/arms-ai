from __future__ import annotations

from typing import Any

from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
)

from backend.risk.multi_account_risk_engine_v2 import (
    MultiAccountRiskEngineV2,
)


class TradeRiskValidatorV2:
    """
    Validador final de riesgo antes de ejecutar operaciones.

    Es consciente del instrumento operado y diferencia
    contratos MINI/MICRO, por ejemplo NQ y MNQ.
    """

    def __init__(
        self,
        risk_engine: Any | None = None,
        instrument_engine: Any | None = None,
    ) -> None:

        self.risk_engine = (
            risk_engine
            if risk_engine is not None
            else MultiAccountRiskEngineV2()
        )

        self.instrument_engine = (
            instrument_engine
            if instrument_engine is not None
            else InstrumentProfileEngine()
        )


    def validate_trade(
        self,
        contracts: int,
        risk_amount: float,
        symbol: str | None = None,
    ) -> dict[str, Any]:

        if contracts <= 0:
            raise ValueError(
                "contracts debe ser mayor que cero."
            )

        if risk_amount < 0:
            raise ValueError(
                "risk_amount no puede ser negativo."
            )

        profile = (
            self.risk_engine
            .get_active_risk_profile()
        )

        max_risk = float(
            profile["risk_per_trade"]
        )

        base_max_contracts = int(
            profile["max_contracts"]
        )

        instrument = None
        normalized_symbol = None
        contract_class = None

        if symbol is not None:

            normalized_symbol = (
                str(symbol)
                .strip()
                .upper()
            )

            if not normalized_symbol:
                raise ValueError(
                    "symbol no puede estar vacío."
                )

            instrument = (
                self.instrument_engine
                .get_profile(
                    symbol=normalized_symbol
                )
            )

            contract_class = (
                instrument.get(
                    "contract_class"
                )
            )

        allowed_contracts = (
            base_max_contracts
        )

        if contract_class == "MICRO":

            configured_limit = (
                profile.get(
                    "max_micro_contracts"
                )
            )

            allowed_contracts = int(
                configured_limit
                if configured_limit is not None
                else base_max_contracts
            )

        elif contract_class == "MINI":

            configured_limit = (
                profile.get(
                    "max_mini_contracts"
                )
            )

            allowed_contracts = int(
                configured_limit
                if configured_limit is not None
                else base_max_contracts
            )

        elif contract_class is None:

            # Compatibilidad temporal para callers
            # legacy que todavía no envían symbol.
            allowed_contracts = (
                base_max_contracts
            )

        else:

            return {
                "status": "BLOCKED",
                "reason":
                    "UNSUPPORTED_CONTRACT_CLASS",
                "symbol":
                    normalized_symbol,
                "contract_class":
                    contract_class,
            }


        if contracts > allowed_contracts:

            return {
                "status": "BLOCKED",
                "reason":
                    "MAX_CONTRACTS_EXCEEDED",
                "allowed_contracts":
                    allowed_contracts,
                "base_max_contracts":
                    base_max_contracts,
                "symbol":
                    normalized_symbol,
                "contract_class":
                    contract_class,
            }


        if risk_amount > max_risk:

            return {
                "status": "BLOCKED",
                "reason":
                    "RISK_LIMIT_EXCEEDED",
                "allowed_risk":
                    max_risk,
                "symbol":
                    normalized_symbol,
                "contract_class":
                    contract_class,
            }


        result = {
            "status": "APPROVED",
            "account":
                profile["account"],
            "account_size":
                profile["account_size"],
            "risk_used":
                float(risk_amount),
            "contracts":
                contracts,
            "allowed_contracts":
                allowed_contracts,
            "base_max_contracts":
                base_max_contracts,
        }

        if normalized_symbol is not None:

            result.update(
                {
                    "symbol":
                        normalized_symbol,
                    "contract_class":
                        contract_class,
                    "instrument_family":
                        instrument.get(
                            "family"
                        ),
                    "point_value":
                        instrument.get(
                            "point_value"
                        ),
                    "tick_size":
                        instrument.get(
                            "tick_size"
                        ),
                    "tick_value":
                        instrument.get(
                            "tick_value"
                        ),
                }
            )

        return result

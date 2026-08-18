from __future__ import annotations

from typing import Any


from backend.risk.trade_risk_validator_v2 import (
    TradeRiskValidatorV2,
)

from backend.risk.risk_event_logger_v1 import (
    RiskEventLoggerV1,
)


class ExecutionRiskGateV1:
    """
    Filtro final de seguridad antes de enviar
    una operación al motor de ejecución.

    Responsabilidades:

    - validar contratos y riesgo;
    - bloquear operaciones inválidas;
    - registrar automáticamente cada decisión;
    - exponer el historial de eventos de riesgo.
    """


    def __init__(
        self,
        validator: Any | None = None,
        logger: Any | None = None,
    ) -> None:

        self.validator = (
            validator
            if validator is not None
            else TradeRiskValidatorV2()
        )

        self.logger = (
            logger
            if logger is not None
            else RiskEventLoggerV1()
        )


    def evaluate_trade(
        self,
        symbol: str,
        side: str,
        contracts: int,
        risk_amount: float,
    ) -> dict[str, Any]:

        normalized_symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        normalized_side = (
            str(side)
            .strip()
            .upper()
        )

        if not normalized_symbol:

            raise ValueError(
                "symbol no puede estar vacío."
            )

        if normalized_side not in {
            "BUY",
            "SELL",
        }:

            raise ValueError(
                "side debe ser BUY o SELL."
            )

        if contracts <= 0:

            raise ValueError(
                "contracts debe ser mayor que cero."
            )

        if risk_amount < 0:

            raise ValueError(
                "risk_amount no puede ser negativo."
            )


        validation = (
            self.validator
            .validate_trade(
                contracts=contracts,
                risk_amount=risk_amount,
            )
        )


        if not isinstance(
            validation,
            dict,
        ):

            raise TypeError(
                "TradeRiskValidatorV2 debe devolver dict."
            )


        status = (
            str(
                validation.get(
                    "status",
                    "",
                )
            )
            .strip()
            .upper()
        )


        if status != "APPROVED":

            reason = (
                validation.get(
                    "reason",
                    "RISK_VALIDATION_FAILED",
                )
            )

            event = {
                "symbol":
                    normalized_symbol,

                "side":
                    normalized_side,

                "contracts":
                    contracts,

                "risk":
                    float(
                        risk_amount
                    ),

                "status":
                    "BLOCKED",

                "reason":
                    reason,
            }


            logged_event = (
                self.logger
                .log_event(
                    event
                )
            )


            return {
                "execution":
                    "BLOCKED",

                "symbol":
                    normalized_symbol,

                "side":
                    normalized_side,

                "contracts":
                    contracts,

                "risk":
                    float(
                        risk_amount
                    ),

                "reason":
                    reason,

                "validation":
                    validation,

                "risk_event":
                    logged_event,
            }


        account = (
            validation.get(
                "account"
            )
        )


        event = {
            "symbol":
                normalized_symbol,

            "side":
                normalized_side,

            "contracts":
                contracts,

            "risk":
                float(
                    risk_amount
                ),

            "status":
                "APPROVED",

            "account":
                account,
        }


        logged_event = (
            self.logger
            .log_event(
                event
            )
        )


        return {
            "execution":
                "APPROVED",

            "symbol":
                normalized_symbol,

            "side":
                normalized_side,

            "contracts":
                contracts,

            "risk":
                float(
                    risk_amount
                ),

            "account":
                account,

            "validation":
                validation,

            "risk_event":
                logged_event,
        }


    def get_risk_events(
        self,
    ) -> list[dict[str, Any]]:

        return list(
            self.logger
            .get_events()
        )

from dataclasses import dataclass


@dataclass
class PositionSizeResult:

    contracts: int

    risk_amount: float

    stop_distance: float

    reason: str



class PositionSizerV1:
    """
    Calcula tamaño de posición ARMS AI.

    Fórmula:

    contratos =
    riesgo permitido /
    (stop puntos * valor punto)
    """


    def calculate(
        self,
        *,
        account_balance: float,
        risk_percent: float,
        entry: float,
        stop_loss: float,
        point_value: float,
    ) -> PositionSizeResult:


        risk_amount = (
            account_balance
            *
            (
                risk_percent / 100
            )
        )


        stop_distance = abs(
            entry - stop_loss
        )


        if stop_distance <= 0:

            return PositionSizeResult(
                contracts=0,
                risk_amount=risk_amount,
                stop_distance=0,
                reason="INVALID STOP",
            )


        raw_contracts = (
            risk_amount
            /
            (
                stop_distance
                *
                point_value
            )
        )


        contracts = int(
            raw_contracts
        )


        if contracts < 1:

            contracts = 1


        return PositionSizeResult(
            contracts=contracts,
            risk_amount=risk_amount,
            stop_distance=stop_distance,
            reason="POSITION CALCULATED",
        )

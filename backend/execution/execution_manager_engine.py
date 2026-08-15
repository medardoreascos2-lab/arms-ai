from dataclasses import dataclass
from typing import List


@dataclass
class ExecutionPlan:

    status: str

    symbol: str

    direction: str

    order_type: str

    contracts: int

    entry: float

    stop_loss: float

    take_profit: float

    risk_amount: float

    validation: List[str]



class ExecutionManagerEngine:


    def __init__(self):
        pass



    def prepare_order(

        self,

        symbol: str,

        direction: str,

        entry: float,

        stop_loss: float,

        take_profit: float,

        contracts: int,

        risk_amount: float,

        approved: bool = True,

    ) -> ExecutionPlan:


        checks = []

        status = "READY"



        if approved:

            checks.append(
                "Execution approval confirmed"
            )

        else:

            status = "BLOCKED"

            checks.append(
                "Execution approval rejected"
            )



        if contracts > 0:

            checks.append(
                "Position size validated"
            )

        else:

            status = "BLOCKED"

            checks.append(
                "Invalid contracts"
            )



        if stop_loss != entry and take_profit != entry:

            checks.append(
                "Risk levels validated"
            )

        else:

            status = "BLOCKED"

            checks.append(
                "Invalid price levels"
            )



        if status == "READY":

            order_type = "LIMIT"

        else:

            order_type = "NONE"



        return ExecutionPlan(

            status=status,

            symbol=symbol,

            direction=direction,

            order_type=order_type,

            contracts=contracts,

            entry=entry,

            stop_loss=stop_loss,

            take_profit=take_profit,

            risk_amount=risk_amount,

            validation=checks,

        )

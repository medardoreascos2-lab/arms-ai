from dataclasses import dataclass
from typing import List



@dataclass
class TradeExecutionReport:

    symbol: str

    direction: str

    entry: float

    stop_loss: float

    take_profit: float

    risk_amount: float

    reward_amount: float

    risk_reward_ratio: float

    contracts: int

    execution_status: str

    approved: bool

    reasoning: List[str]




class TradeExecutionIntelligence:



    def __init__(self):

        pass



    def analyze(

        self,

        symbol: str,

        direction: str,

        entry: float,

        stop_loss: float,

        take_profit: float,

        account_size: float,

        risk_percent: float,

        contract_value: float = 20,

    ) -> TradeExecutionReport:



        reasoning = []



        risk_amount = (

            account_size

            *

            risk_percent

            /

            100

        )



        stop_distance = abs(

            entry - stop_loss

        )


        reward_distance = abs(

            take_profit - entry

        )



        if stop_distance > 0:

            risk_reward_ratio = round(

                reward_distance / stop_distance,

                2

            )

        else:

            risk_reward_ratio = 0



        if stop_distance > 0:

            contracts = int(

                risk_amount

                /

                (

                    stop_distance

                    *

                    contract_value

                )

            )

        else:

            contracts = 0



        if risk_reward_ratio >= 2:

            reasoning.append(

                "Risk Reward aprobado."

            )

        else:

            reasoning.append(

                "Risk Reward insuficiente."

            )



        if contracts > 0:

            reasoning.append(

                "Tamaño de posición calculado."

            )

        else:

            reasoning.append(

                "No existe tamaño válido."

            )



        approved = (

            risk_reward_ratio >= 2

            and

            contracts > 0

        )



        if approved:

            execution_status = "READY"

            reasoning.append(

                "Operación lista para ejecución."

            )

        else:

            execution_status = "BLOCKED"

            reasoning.append(

                "Operación bloqueada."

            )



        return TradeExecutionReport(

            symbol=symbol,

            direction=direction,

            entry=entry,

            stop_loss=stop_loss,

            take_profit=take_profit,

            risk_amount=risk_amount,

            reward_amount=(

                risk_amount

                *

                risk_reward_ratio

            ),

            risk_reward_ratio=risk_reward_ratio,

            contracts=contracts,

            execution_status=execution_status,

            approved=approved,

            reasoning=reasoning,

        )

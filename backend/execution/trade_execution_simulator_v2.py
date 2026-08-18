from dataclasses import dataclass
from typing import List



@dataclass
class SimulatedTrade:

    symbol: str

    direction: str

    entry: float

    stop_loss: float

    take_profit: float

    contracts: int

    risk_amount: float

    status: str

    pnl: float

    reasoning: List[str]




class TradeExecutionSimulatorV2:



    def __init__(self):

        pass



    def execute(

        self,

        symbol: str,

        direction: str,

        entry: float,

        stop_loss: float,

        take_profit: float,

        contracts: int,

        risk_amount: float,

        approved: bool,

    ) -> SimulatedTrade:



        reasoning = []



        if not approved:

            return SimulatedTrade(

                symbol=symbol,

                direction=direction,

                entry=entry,

                stop_loss=stop_loss,

                take_profit=take_profit,

                contracts=contracts,

                risk_amount=risk_amount,

                status="BLOCKED",

                pnl=0.0,

                reasoning=[

                    "Operación rechazada por validación AI."

                ],

            )



        reasoning.append(

            "Trade aprobado por ARMS AI."

        )


        reasoning.append(

            "Ejecución simulada creada."

        )



        return SimulatedTrade(

            symbol=symbol,

            direction=direction,

            entry=entry,

            stop_loss=stop_loss,

            take_profit=take_profit,

            contracts=contracts,

            risk_amount=risk_amount,

            status="OPEN",

            # Realized PnL remains zero
            # until the position is closed.
            pnl=0.0,

            reasoning=reasoning,

        )

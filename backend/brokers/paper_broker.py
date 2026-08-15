from dataclasses import dataclass
from datetime import datetime



@dataclass
class ExecutionReport:

    status: str

    order_id: str

    symbol: str

    direction: str

    filled_price: float

    contracts: int

    timestamp: str



class PaperBroker:


    def __init__(self):

        self.counter = 1



    def submit_order(
        self,
        order
    ) -> ExecutionReport:


        order_id = (
            f"PAPER-{self.counter}"
        )

        self.counter += 1



        return ExecutionReport(

            status="FILLED",

            order_id=order_id,

            symbol=order.symbol,

            direction=order.direction,

            filled_price=order.entry,

            contracts=order.contracts,

            timestamp=datetime.utcnow().isoformat(),

        )

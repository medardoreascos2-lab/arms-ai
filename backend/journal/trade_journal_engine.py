from dataclasses import dataclass
from typing import List
from datetime import datetime

from backend.storage.journal_database import (
    JournalDatabase,
)



@dataclass
class TradeRecord:

    order_id: str

    symbol: str

    direction: str

    entry: float

    stop_loss: float

    take_profit: float

    contracts: int

    status: str

    strategy: str

    confidence: int

    timestamp: str



class TradeJournalEngine:


    def __init__(self):

        self.trades: List[TradeRecord] = []

        self.database = JournalDatabase()



    def record_trade(

        self,

        execution_report,

        order,

        strategy: str = "EMA50 Smart Money",

        confidence: int = 98,

    ) -> TradeRecord:


        trade = TradeRecord(

            order_id=execution_report.order_id,

            symbol=execution_report.symbol,

            direction=execution_report.direction,

            entry=execution_report.filled_price,

            stop_loss=order.stop_loss,

            take_profit=order.take_profit,

            contracts=execution_report.contracts,

            status=execution_report.status,

            strategy=strategy,

            confidence=confidence,

            timestamp=datetime.utcnow().isoformat(),

        )


        self.trades.append(
            trade
        )


        self.database.save_trade(
            trade
        )


        return trade



    def get_history(self):

        return self.trades

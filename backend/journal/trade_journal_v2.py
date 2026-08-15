from dataclasses import dataclass
from typing import List



@dataclass
class TradeJournalEntry:

    trade_id: str

    symbol: str

    direction: str

    entry: float

    stop_loss: float

    take_profit: float

    contracts: int

    risk_amount: float

    status: str

    result: str

    pnl: float

    reasoning: List[str]




class TradeJournalV2:



    def __init__(

        self,

        analytics_v2=None,

        *args,

        **kwargs

    ):

        self.trades = []

        self.analytics_v2 = analytics_v2



    def record(

        self,

        trade_id: str,

        symbol: str,

        direction: str,

        entry: float,

        stop_loss: float,

        take_profit: float,

        contracts: int,

        risk_amount: float,

        status: str,

    ) -> TradeJournalEntry:



        reasoning = [

            "Trade registrado en ARMS AI Journal.",

            "Operación almacenada para aprendizaje."

        ]



        trade = TradeJournalEntry(

            trade_id=trade_id,

            symbol=symbol,

            direction=direction,

            entry=entry,

            stop_loss=stop_loss,

            take_profit=take_profit,

            contracts=contracts,

            risk_amount=risk_amount,

            status=status,

            result="OPEN",

            pnl=0,

            reasoning=reasoning,

        )


        self.trades.append(trade)


        return trade



    def record_open_trade(
        self,
        trade: dict,
    ):

        entry = TradeJournalEntry(

            trade_id=str(
                trade.get(
                    "trade_id",
                    "",
                )
            ),

            symbol=str(
                trade.get(
                    "symbol",
                    "",
                )
            ),

            direction=str(
                trade.get(
                    "direction",
                    "",
                )
            ),

            entry=float(
                trade.get(
                    "entry_price",
                    0.0,
                )
            ),

            stop_loss=float(
                trade.get(
                    "stop_loss",
                    0.0,
                )
                or 0.0
            ),

            take_profit=float(
                trade.get(
                    "take_profit",
                    0.0,
                )
                or 0.0
            ),

            contracts=int(
                trade.get(
                    "quantity",
                    0,
                )
            ),

            risk_amount=0.0,

            status="OPEN",

            result="OPEN",

            pnl=0.0,

            reasoning=[
                "Trade abierto mediante TradeLifecycleServiceV2.",
                "Operación registrada en Journal central.",
            ],

        )


        self.trades.append(
            entry
        )


        return entry



    def history(self):

        return self.trades



    def get_trades(self):

        return self.trades



    def get_open_trades(self):

        return [

            trade

            for trade in self.trades

            if trade.status == "OPEN"

        ]



    def get_closed_trades(self):

        return [

            trade

            for trade in self.trades

            if trade.status != "OPEN"

        ]




    def close_trade(
        self,
        trade_id: str,
        result: str = "CLOSED",
        pnl: float = 0.0,
        exit_price: float | None = None,
        exit_time=None,
        exit_reason: str | None = None,
        point_value: float = 1.0,
    ):

        for trade in self.trades:

            if trade.trade_id == trade_id:

                trade.status = "CLOSED"

                trade.result = (
                    result
                )

                if (
                    exit_price is not None
                ):
                    if trade.direction.upper() == "LONG":
                        calculated_pnl = (
                            float(exit_price)
                            - float(trade.entry)
                        ) * int(trade.contracts) * float(point_value)

                    else:
                        calculated_pnl = (
                            float(trade.entry)
                            - float(exit_price)
                        ) * int(trade.contracts) * float(point_value)

                    trade.pnl = (
                        round(
                            calculated_pnl,
                            2
                        )
                    )

                else:
                    trade.pnl = (
                        float(pnl)
                    )

                if exit_reason:

                    trade.reasoning.append(
                        f"Trade cerrado: {exit_reason}"
                    )

                else:

                    trade.reasoning.append(
                        "Trade actualizado con resultado final."
                    )

                return trade


        return None



    def get_summary(self):

        total_trades = len(
            self.trades
        )


        open_trades = len(

            [

                trade

                for trade in self.trades

                if trade.status == "OPEN"

            ]

        )


        closed_trades = len(

            [

                trade

                for trade in self.trades

                if trade.status != "OPEN"

            ]

        )


        return {

            "total_trades":
                total_trades,

            "open_trades":
                open_trades,

            "closed_trades":
                closed_trades,

        }

    def get_analytics(self):
        if self.analytics_v2 is None:
            return {}

        trades = [
            {
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "direction": trade.direction,
                "entry_price": trade.entry,
                "exit_price": 0.0,
                "quantity": trade.contracts,
                "realized_pnl": trade.pnl,
                "result": trade.result,
            }
            for trade in self.trades
        ]

        return self.analytics_v2.analyze(
            trades=trades,
            starting_balance=17000.0,
        )


    def get_breakdown(self):

        analytics = self.get_analytics()

        if not analytics:
            return {}

        return {
            "wins": analytics.get(
                "wins",
                0,
            ),
            "losses": analytics.get(
                "losses",
                0,
            ),
            "break_even": analytics.get(
                "break_even",
                0,
            ),
            "win_rate": analytics.get(
                "win_rate",
                0.0,
            ),
        }


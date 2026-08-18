from dataclasses import dataclass, field
from datetime import datetime
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

    


    position_id: str = ""

    created_at: datetime = field(
        default_factory=datetime.now
    )

    exit_reason: str = ""

    exit_price: float = 0.0

    closed_at: datetime | None = None

    def __getitem__(self, key):

        aliases = {
            "quantity": "contracts",
            "entry_price": "entry",
            "entry_time": "created_at",
            "exit_reason": "exit_reason",
            "exit_price": "exit_price",
            "closed_at": "closed_at",
            "realized_pnl": "pnl",
            "stop": "stop_loss",
            "target": "take_profit",
        }

        key = aliases.get(
            key,
            key,
        )

        return getattr(
            self,
            key,
        )

    def get(
        self,
        key,
        default=None,
    ):

        aliases = {
            "quantity": "contracts",
            "entry_price": "entry",
            "entry_time": "created_at",
            "exit_reason": "exit_reason",
            "exit_price": "exit_price",
            "closed_at": "closed_at",
            "realized_pnl": "pnl",
            "stop": "stop_loss",
            "target": "take_profit",
        }

        key = aliases.get(
            key,
            key,
        )

        return getattr(
            self,
            key,
            default,
        )





class TradeJournalV2:



    def __init__(

        self,

        analytics_v2=None,
        breakdown_analytics_v2=None,
        breakdown_analytics=None,

        *args,

        **kwargs

    ):

        self.trades = []

        if (
            analytics_v2 is not None
            and not hasattr(
                analytics_v2,
                "calculate",
            )
        ):
            raise TypeError(
                "analytics_v2 debe implementar calculate."
            )

        self.analytics_v2 = analytics_v2

        if breakdown_analytics_v2 is None:
            breakdown_analytics_v2 = (
                breakdown_analytics
            )

        if (
            breakdown_analytics_v2 is not None
            and not hasattr(
                breakdown_analytics_v2,
                "calculate",
            )
        ):
            raise TypeError(
                "breakdown_analytics_v2 debe implementar calculate."
            )

        self.breakdown_analytics_v2 = (
            breakdown_analytics_v2
        )



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

            position_id=str(
                trade.get(
                    "position_id",
                    "",
                )
            ),

            created_at=datetime.now(),

            exit_reason=str(
                trade.get(
                    "exit_reason",
                    "",
                )
            ),

            exit_price=float(
                trade.get(
                    "exit_price",
                    0.0,
                )
                or 0.0
            ),

            closed_at=None,

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

                supplied_pnl = float(
                    pnl
                )

                if supplied_pnl != 0.0:
                    trade.pnl = round(
                        supplied_pnl,
                        2,
                    )

                elif (
                    exit_price is not None
                ):
                    if trade.direction.upper() == "LONG":
                        calculated_pnl = (
                            float(exit_price)
                            - float(trade.entry)
                        ) * float(trade.contracts) * float(point_value)

                    else:
                        calculated_pnl = (
                            float(trade.entry)
                            - float(exit_price)
                        ) * float(trade.contracts) * float(point_value)

                    trade.pnl = round(
                        calculated_pnl,
                        2,
                    )

                else:
                    trade.pnl = supplied_pnl

                trade.exit_price = float(
                    exit_price
                    if exit_price is not None
                    else 0.0
                )

                trade.closed_at = (
                    exit_time
                    if exit_time is not None
                    else datetime.now()
                )

                if exit_reason:

                    trade.exit_reason = str(
                        exit_reason
                    )

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

            "analytics":
                self.get_analytics(),

            "breakdown":
                self.get_breakdown(),

        }

    def get_analytics(self):
        if self.analytics_v2 is None:
            return None

        source_trades = getattr(
            self,
            "_closed_trades",
            self.trades,
        )

        trades = []

        for trade in source_trades:
            if isinstance(
                trade,
                dict,
            ):
                trades.append(
                    trade
                )

            else:
                trades.append(
                    {
                        "trade_id": trade.trade_id,
                        "symbol": trade.symbol,
                        "direction": trade.direction,
                        "entry_price": trade.entry,
                        "exit_price": 0.0,
                        "quantity": trade.contracts,
                        "realized_pnl": trade.pnl,
                        "status": trade.status,
                        "result": trade.result,
                    }
                )

        return self.analytics_v2.calculate(
            trades=trades,
        )



    def get_breakdown(self):

        if self.breakdown_analytics_v2 is None:
            return None

        source_trades = getattr(
            self,
            "_closed_trades",
            self.trades,
        )

        trades = []

        for trade in source_trades:
            if isinstance(
                trade,
                dict,
            ):
                trades.append(
                    trade
                )

            else:
                trades.append(
                    {
                        "trade_id": trade.trade_id,
                        "symbol": trade.symbol,
                        "direction": trade.direction,
                        "session": "",
                        "strategy": "",
                        "timeframe": "",
                        "exit_reason": "",
                        "realized_pnl": trade.pnl,
                        "status": trade.status,
                    }
                )

        return self.breakdown_analytics_v2.calculate(
            trades=trades,
        )


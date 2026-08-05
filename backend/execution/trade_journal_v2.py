
from __future__ import annotations



class TradeJournalV2:
    """
    Historial interno de operaciones de ARMS AI.

    Guarda operaciones registradas y permite
    consultar el historial.
    """



    def __init__(
        self,
    ):

        self._trades = []



    def add_trade(
        self,
        trade: dict | None,
    ) -> dict:



        if not isinstance(
            trade,
            dict,
        ):

            return {
                "status": "BLOCKED",
                "reason": "INVALID_TRADE",
            }



        if not trade.get(
            "trade_id"
        ):

            return {
                "status": "BLOCKED",
                "reason": "INVALID_TRADE",
            }



        self._trades.append(
            trade
        )



        return {
            "status": "RECORDED",
            "trade": trade,
        }



    def get_trades(
        self,
    ) -> list:



        return list(
            self._trades
        )

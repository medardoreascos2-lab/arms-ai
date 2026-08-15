from typing import List


class TradeHistoryAdapter:


    def __init__(self):
        pass



    def convert_database_trades(
        self,
        database_trades: List
    ):


        trades = []


        for row in database_trades:


            class TradeResult:


                def __init__(
                    self,
                    profit,
                    direction,
                    symbol,
                    strategy
                ):

                    self.profit = profit

                    self.direction = direction

                    self.symbol = symbol

                    self.strategy = strategy



            symbol = row[2]

            direction = row[3]

            entry = row[4]

            take_profit = row[6]

            strategy = row[9]



            if direction == "BUY":

                profit = (
                    take_profit - entry
                )

            else:

                profit = (
                    entry - take_profit
                )



            trades.append(

                TradeResult(

                    profit=profit,

                    direction=direction,

                    symbol=symbol,

                    strategy=strategy,

                )

            )


        return trades

class BacktestExecutionSimulatorV2:
    """
    Simula ejecución profesional
    de operaciones ARMS AI.
    """

    def simulate(
        self,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        candles,
    ) -> dict:

        exit_price = None
        result = "NO_RESULT"
        exit_reason = "END_OF_DATA"
        bars_held = 0


        for index, candle in enumerate(candles, start=1):

            bars_held = index


            if direction == "BUY":

                if candle.low <= stop_loss:
                    exit_price = stop_loss
                    result = "LOSS"
                    exit_reason = "STOP_LOSS"
                    break


                if candle.high >= take_profit:
                    exit_price = take_profit
                    result = "WIN"
                    exit_reason = "TAKE_PROFIT"
                    break


            elif direction == "SELL":

                if candle.high >= stop_loss:
                    exit_price = stop_loss
                    result = "LOSS"
                    exit_reason = "STOP_LOSS"
                    break


                if candle.low <= take_profit:
                    exit_price = take_profit
                    result = "WIN"
                    exit_reason = "TAKE_PROFIT"
                    break


        if exit_price is None:

            exit_price = candles[-1].close


        if direction == "BUY":

            pnl = (
                exit_price - entry
            )

            risk = (
                entry - stop_loss
            )


        elif direction == "SELL":

            pnl = (
                entry - exit_price
            )

            risk = (
                stop_loss - entry
            )


        else:
            return {}


        rr = (
            pnl / risk
            if risk > 0
            else 0
        )


        return {
            "direction": direction,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "exit_price": exit_price,
            "pnl": pnl,
            "rr": rr,
            "result": result,
            "exit_reason": exit_reason,
            "bars_held": bars_held,
        }

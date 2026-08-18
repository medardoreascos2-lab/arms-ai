from backend.execution.trade_execution_simulator_v2 import (
    SimulatedTrade,
)

from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
)


class BacktestExecutionSimulatorV2:
    """
    Simula ejecución profesional
    de operaciones ARMS AI.
    """

    def simulate(
        self,
        symbol: str,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        contracts: int,
        risk_amount: float,
        candles,
    ) -> SimulatedTrade:

        normalized_symbol = str(
            symbol
        ).strip().upper()

        if not normalized_symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        profile = (
            InstrumentProfileEngine()
            .get_profile(
                symbol=normalized_symbol
            )
        )

        point_value = float(
            profile["point_value"]
        )

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

            if not candles:
                return SimulatedTrade(
                    symbol=normalized_symbol,
                    direction=direction,
                    entry=entry,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    contracts=contracts,
                    risk_amount=risk_amount,
                    status="NO_DATA",
                    pnl=0.0,
                    reasoning=[
                        "No hay velas futuras para evaluar."
                    ],
                )


            exit_price = candles[-1].close


        if direction == "BUY":

            pnl = (
                (
                    exit_price - entry
                )
                *
                contracts
                * point_value
            )

            risk = (
                (
                    entry - stop_loss
                )
                * contracts
                * point_value
            )


        elif direction == "SELL":

            pnl = (
                (
                    entry - exit_price
                )
                *
                contracts
                * point_value
            )

            risk = (
                (
                    stop_loss - entry
                )
                * contracts
                * point_value
            )


        else:
            return {}


        rr = (
            pnl / risk
            if risk > 0
            else 0
        )


        return SimulatedTrade(
            symbol=normalized_symbol,
            direction=direction,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            contracts=contracts,
            risk_amount=risk_amount,
            status=result,
            pnl=float(
                pnl
            ),
            reasoning=[
                exit_reason,
                f"RR={rr}",
                f"BARS={bars_held}",
            ],
        )

from __future__ import annotations


from datetime import datetime

from backend.models.candle import Candle


class BacktestEnginePipelineAdapterV2:
    """
    Adaptador entre BacktestEngine
    y BacktestPipelineV2.
    """

    def __init__(
        self,
        *,
        pipeline,
    ) -> None:

        self.pipeline = pipeline


    def run(
        self,
        *,
        initial_context,
    ):

        raw_candles = (
            initial_context
            .get(
                "backtest_candles",
                []
            )
        )


        candles = []

        for item in raw_candles:

            if isinstance(item, Candle):
                candles.append(item)
                continue


            price = float(
                item.get(
                    "price",
                    0
                )
            )

            candles.append(
                Candle(
                    symbol="NQ",
                    timeframe="1m",
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=float(
                        item.get(
                            "volume",
                            0
                        )
                    ),
                    timestamp=datetime.now(),
                )
            )


        session = (
            self.pipeline
            .backtest_session_v2
        )


        future_candles = (
            initial_context.get(
                "future_candles",
                []
            )
        )


        normalized_future = []


        for item in future_candles:


            if isinstance(
                item,
                Candle,
            ):

                normalized_future.append(
                    item
                )

                continue



            price = float(
                item.get(
                    "price",
                    item.get(
                        "close",
                        0,
                    ),
                )
            )


            normalized_future.append(
                Candle(
                    symbol="NQ",
                    timeframe="1m",
                    open=price,
                    high=float(
                        item.get(
                            "high",
                            price,
                        )
                    ),
                    low=float(
                        item.get(
                            "low",
                            price,
                        )
                    ),
                    close=price,
                    volume=float(
                        item.get(
                            "volume",
                            0,
                        )
                    ),
                    timestamp=datetime.now(),
                )
            )


        session.future_candles = (
            normalized_future
        )


        session.backtest_runner_v2.replay_engine_v2.load(
            candles
        )


        session.run()


        context = {
            "trade_plan": None,
            "simulated_trade": None,
            "signals": session.signals,
            "submission_results": session.submission_results,
            "decisions": session.decisions,
        }


        if session.trade_plans:
            context["trade_plan"] = (
                session.trade_plans[-1]
            )


        if session.simulated_trades:
            context["simulated_trade"] = (
                session.simulated_trades[-1]
            )


        return context

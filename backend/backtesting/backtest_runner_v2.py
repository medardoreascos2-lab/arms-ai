from __future__ import annotations


class BacktestRunnerV2:
    """
    Coordina la reproducción completa de velas históricas
    y las publica en el pipeline de datos del mercado.
    """

    def __init__(
        self,
        *,
        replay_engine_v2,
        replay_market_data_bridge_v2,
    ) -> None:

        required_replay_methods = (
            "current",
            "has_next",
            "next",
            "reset",
        )

        for method_name in required_replay_methods:
            if not callable(
                getattr(
                    replay_engine_v2,
                    method_name,
                    None,
                )
            ):
                raise TypeError(
                    "replay_engine_v2 debe implementar "
                    f"{method_name}()."
                )

        if not callable(
            getattr(
                replay_market_data_bridge_v2,
                "publish",
                None,
            )
        ):
            raise TypeError(
                "replay_market_data_bridge_v2 debe "
                "implementar publish()."
            )

        self.replay_engine_v2 = replay_engine_v2
        self.replay_market_data_bridge_v2 = (
            replay_market_data_bridge_v2
        )

    def run(self) -> int:
        """
        Reinicia el replay y publica todas las velas.

        Devuelve la cantidad total de velas publicadas.
        """

        self.replay_engine_v2.reset()

        processed_count = 0

        current_candle = (
            self.replay_engine_v2.current()
        )

        if current_candle is None:
            return processed_count

        self.replay_market_data_bridge_v2.publish(
            current_candle
        )

        processed_count += 1

        while self.replay_engine_v2.has_next():
            candle = self.replay_engine_v2.next()

            self.replay_market_data_bridge_v2.publish(
                candle
            )

            processed_count += 1

        return processed_count

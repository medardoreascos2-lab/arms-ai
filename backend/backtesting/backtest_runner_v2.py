from __future__ import annotations

from collections.abc import Callable
from typing import Any


class BacktestRunnerV2:
    """
    Coordina la reproducción completa de velas históricas
    y las publica en el pipeline de datos del mercado.

    Opcionalmente notifica a un observador después de
    publicar cada vela.
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

    def run(
        self,
        *,
        on_candle: Callable[[Any, Any], None] | None = None,
    ) -> int:
        """
        Reinicia el replay y publica todas las velas.

        Si se proporciona on_candle, se ejecuta después
        de publicar cada vela y recibe:

        - candle
        - publish_result

        Devuelve la cantidad total de velas publicadas.
        """

        if on_candle is not None and not callable(on_candle):
            raise TypeError(
                "on_candle debe ser callable o None."
            )

        self.replay_engine_v2.reset()

        processed_count = 0

        current_candle = (
            self.replay_engine_v2.current()
        )

        if current_candle is None:
            return processed_count

        publish_result = (
            self.replay_market_data_bridge_v2.publish(
                current_candle
            )
        )

        if on_candle is not None:
            on_candle(
                current_candle,
                publish_result,
            )

        processed_count += 1

        while self.replay_engine_v2.has_next():
            candle = self.replay_engine_v2.next()

            publish_result = (
                self.replay_market_data_bridge_v2.publish(
                    candle
                )
            )

            if on_candle is not None:
                on_candle(
                    candle,
                    publish_result,
                )

            processed_count += 1

        return processed_count

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone


class PriceFeedServiceV2:

    def __init__(
        self,
        *,
        live_position_monitor_v2=None,
    ) -> None:

        if (
            live_position_monitor_v2
            is not None
            and not callable(
                getattr(
                    live_position_monitor_v2,
                    "process_price",
                    None,
                )
            )
        ):
            raise TypeError(
                "live_position_monitor_v2 debe "
                "implementar process_price()."
            )

        self.live_position_monitor_v2 = (
            live_position_monitor_v2
        )

        self._state = {
            "price_count": 0,
            "last_symbol": None,
            "last_price": None,
            "last_source": None,
            "last_received_at": None,
            "monitor_calls": 0,
            "monitor_errors": 0,
        }

    def process_price(
        self,
        *,
        symbol: str,
        current_price: float,
        source: str,
    ) -> dict[str, object]:

        normalized_symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol es obligatorio."
            )

        normalized_price = float(
            current_price
        )

        if normalized_price <= 0:
            raise ValueError(
                "current_price debe ser "
                "mayor que cero."
            )

        normalized_source = (
            str(source)
            .strip()
            .upper()
        )

        if not normalized_source:
            raise ValueError(
                "source es obligatorio."
            )

        received_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        self._state["price_count"] += 1
        self._state["last_symbol"] = (
            normalized_symbol
        )
        self._state["last_price"] = (
            normalized_price
        )
        self._state["last_source"] = (
            normalized_source
        )
        self._state["last_received_at"] = (
            received_at
        )

        monitor_processed = False
        monitor_error = False
        monitor_result = None

        if (
            self.live_position_monitor_v2
            is not None
        ):
            self._state[
                "monitor_calls"
            ] += 1

            try:
                monitor_result = (
                    self.live_position_monitor_v2
                    .process_price(
                        symbol=normalized_symbol,
                        current_price=(
                            normalized_price
                        ),
                    )
                )

                if not isinstance(
                    monitor_result,
                    dict,
                ):
                    raise TypeError(
                        "process_price() debe "
                        "devolver un dict."
                    )

                monitor_processed = True

            except Exception:
                self._state[
                    "monitor_errors"
                ] += 1

                monitor_error = True
                monitor_result = None

        return {
            "processed": True,
            "symbol": normalized_symbol,
            "current_price": normalized_price,
            "source": normalized_source,
            "received_at": received_at,
            "monitor_processed": (
                monitor_processed
            ),
            "monitor_error": (
                monitor_error
            ),
            "monitor_result": deepcopy(
                monitor_result
            ),
        }

    def get_state(
        self,
    ) -> dict[str, object]:

        return deepcopy(
            self._state
        )

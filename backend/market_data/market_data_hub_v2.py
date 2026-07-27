from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone


class MarketDataHubV2:

    def __init__(
        self,
        *,
        price_feed_service_v2=None,
        reject_duplicates: bool = True,
    ) -> None:

        if (
            price_feed_service_v2
            is not None
            and not callable(
                getattr(
                    price_feed_service_v2,
                    "process_price",
                    None,
                )
            )
        ):
            raise TypeError(
                "price_feed_service_v2 debe "
                "implementar process_price()."
            )

        if not isinstance(
            reject_duplicates,
            bool,
        ):
            raise TypeError(
                "reject_duplicates debe ser bool."
            )

        self.price_feed_service_v2 = (
            price_feed_service_v2
        )

        self.reject_duplicates = (
            reject_duplicates
        )

        self._last_prices: dict[
            tuple[str, str],
            float,
        ] = {}

        self._state = {
            "message_count": 0,
            "processed_count": 0,
            "duplicate_count": 0,
            "error_count": 0,
            "last_symbol": None,
            "last_price": None,
            "last_source": None,
            "last_received_at": None,
        }

    def process_market_price(
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

        self._state["message_count"] += 1
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

        duplicate_key = (
            normalized_symbol,
            normalized_source,
        )

        previous_price = (
            self._last_prices.get(
                duplicate_key
            )
        )

        if (
            self.reject_duplicates
            and previous_price
            == normalized_price
        ):
            self._state[
                "duplicate_count"
            ] += 1

            return {
                "processed": False,
                "duplicate": True,
                "reason": "duplicate_price",
                "feed_error": False,
                "symbol": normalized_symbol,
                "current_price": normalized_price,
                "source": normalized_source,
                "received_at": received_at,
                "price_feed_result": None,
            }

        if self.price_feed_service_v2 is None:
            return {
                "processed": False,
                "duplicate": False,
                "reason": (
                    "no_price_feed_service"
                ),
                "feed_error": False,
                "symbol": normalized_symbol,
                "current_price": normalized_price,
                "source": normalized_source,
                "received_at": received_at,
                "price_feed_result": None,
            }

        try:
            price_feed_result = (
                self.price_feed_service_v2
                .process_price(
                    symbol=normalized_symbol,
                    current_price=(
                        normalized_price
                    ),
                    source=normalized_source,
                )
            )

            if not isinstance(
                price_feed_result,
                dict,
            ):
                raise TypeError(
                    "process_price() debe "
                    "devolver un dict."
                )

        except Exception:
            self._state[
                "error_count"
            ] += 1

            return {
                "processed": False,
                "duplicate": False,
                "reason": "price_feed_error",
                "feed_error": True,
                "symbol": normalized_symbol,
                "current_price": normalized_price,
                "source": normalized_source,
                "received_at": received_at,
                "price_feed_result": None,
            }

        self._last_prices[
            duplicate_key
        ] = normalized_price

        self._state[
            "processed_count"
        ] += 1

        return {
            "processed": True,
            "duplicate": False,
            "reason": None,
            "feed_error": False,
            "symbol": normalized_symbol,
            "current_price": normalized_price,
            "source": normalized_source,
            "received_at": received_at,
            "price_feed_result": deepcopy(
                price_feed_result
            ),
        }

    def get_state(
        self,
    ) -> dict[str, object]:

        return deepcopy(
            self._state
        )

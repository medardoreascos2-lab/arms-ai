from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone
from math import isfinite


class PriceFeedServiceV2:

    def __init__(
        self,
        *,
        live_position_monitor_v2=None,
        maximum_age_seconds: float | None = None,
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

        if maximum_age_seconds is None:
            self.maximum_age_seconds = None
        else:
            normalized_maximum_age = float(
                maximum_age_seconds
            )
            if (
                not isfinite(normalized_maximum_age)
                or normalized_maximum_age <= 0.0
            ):
                raise ValueError(
                    "maximum_age_seconds debe ser "
                    "finito y mayor que cero."
                )
            self.maximum_age_seconds = (
                normalized_maximum_age
            )

        self._last_operational_timestamp_by_symbol: dict[
            str,
            datetime,
        ] = {}

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
        timestamp: datetime | None = None,
        current_timestamp: datetime | None = None,
        maximum_age_seconds: float | None = None,
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

        operational_source = (
            normalized_source
            in {
                "TRADINGVIEW",
                "TRADINGVIEW_WEBHOOK",
                "BROKER",
                "MARKET_WEBHOOK",
            }
        )

        if timestamp is not None and not isinstance(
            timestamp,
            datetime,
        ):
            raise TypeError(
                "timestamp debe ser datetime."
            )

        if (
            current_timestamp is not None
            and not isinstance(
                current_timestamp,
                datetime,
            )
        ):
            raise TypeError(
                "current_timestamp debe ser datetime."
            )

        normalized_timestamp = timestamp
        if normalized_timestamp is not None:
            if normalized_timestamp.tzinfo is None:
                normalized_timestamp = (
                    normalized_timestamp.replace(
                        tzinfo=timezone.utc
                    )
                )
            else:
                normalized_timestamp = (
                    normalized_timestamp.astimezone(
                        timezone.utc
                    )
                )

        now = (
            current_timestamp
            if current_timestamp is not None
            else datetime.now(timezone.utc)
        )
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)

        effective_maximum_age = (
            self.maximum_age_seconds
            if maximum_age_seconds is None
            else float(maximum_age_seconds)
        )

        if maximum_age_seconds is not None and (
            not isfinite(effective_maximum_age)
            or effective_maximum_age <= 0.0
        ):
            raise ValueError(
                "maximum_age_seconds debe ser "
                "finito y mayor que cero."
            )

        if operational_source:
            if normalized_timestamp is None:
                raise ValueError(
                    "timestamp autoritativo requerido "
                    "para precio operativo."
                )

            if effective_maximum_age is None:
                raise RuntimeError(
                    "maximum_age_seconds no configurado "
                    "para precio operativo."
                )

            age_seconds = (
                now - normalized_timestamp
            ).total_seconds()

            if age_seconds < 0.0:
                raise ValueError(
                    "timestamp futuro no permitido."
                )

            if age_seconds > effective_maximum_age:
                raise ValueError(
                    "precio operativo expirado."
                )

            previous_timestamp = (
                self
                ._last_operational_timestamp_by_symbol
                .get(normalized_symbol)
            )

            if (
                previous_timestamp is not None
                and normalized_timestamp
                <= previous_timestamp
            ):
                raise ValueError(
                    "precio operativo fuera de orden."
                )

        received_at = (
            normalized_timestamp.isoformat()
            if normalized_timestamp is not None
            else now.isoformat()
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

                if (
                    operational_source
                    and normalized_timestamp
                    is not None
                ):
                    self._last_operational_timestamp_by_symbol[
                        normalized_symbol
                    ] = normalized_timestamp

            except Exception:
                self._state[
                    "monitor_errors"
                ] += 1

                monitor_error = True
                monitor_result = None

        if (
            operational_source
            and normalized_timestamp is not None
            and self.live_position_monitor_v2 is None
        ):
            self._last_operational_timestamp_by_symbol[
                normalized_symbol
            ] = normalized_timestamp

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

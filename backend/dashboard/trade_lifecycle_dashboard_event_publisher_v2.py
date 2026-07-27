from __future__ import annotations

from copy import deepcopy


class TradeLifecycleDashboardEventPublisherV2:

    def __init__(
        self,
        *,
        event_bus_v2=None,
    ) -> None:

        if (
            event_bus_v2 is not None
            and not callable(
                getattr(
                    event_bus_v2,
                    "publish",
                    None,
                )
            )
        ):
            raise TypeError(
                "event_bus_v2 debe implementar "
                "publish()."
            )

        self.event_bus_v2 = (
            event_bus_v2
        )

    def _publish(
        self,
        *,
        event_type: str,
        payload: dict[str, object],
        payload_name: str,
    ) -> dict[str, object]:

        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                f"{payload_name} debe ser un dict."
            )

        if self.event_bus_v2 is None:
            return {
                "published": False,
                "reason": "no_event_bus",
                "event_type": event_type,
            }

        result = self.event_bus_v2.publish(
            event_type=event_type,
            payload=deepcopy(
                payload
            ),
        )

        if not isinstance(
            result,
            dict,
        ):
            raise TypeError(
                "event_bus_v2.publish() "
                "debe devolver un dict."
            )

        response = dict(
            result
        )

        response[
            "event_type"
        ] = event_type

        return response

    def publish_trade_opened(
        self,
        *,
        trade: dict[str, object],
    ) -> dict[str, object]:

        return self._publish(
            event_type="trade_opened",
            payload=trade,
            payload_name="trade",
        )

    def publish_trade_closed(
        self,
        *,
        trade: dict[str, object],
    ) -> dict[str, object]:

        return self._publish(
            event_type="trade_closed",
            payload=trade,
            payload_name="trade",
        )

    def publish_position_updated(
        self,
        *,
        position: dict[str, object],
    ) -> dict[str, object]:

        return self._publish(
            event_type="position_updated",
            payload=position,
            payload_name="position",
        )

    def publish_portfolio_updated(
        self,
        *,
        portfolio: dict[str, object],
    ) -> dict[str, object]:

        return self._publish(
            event_type="portfolio_updated",
            payload=portfolio,
            payload_name="portfolio",
        )

    def publish_risk_updated(
        self,
        *,
        risk: dict[str, object],
    ) -> dict[str, object]:

        return self._publish(
            event_type="risk_updated",
            payload=risk,
            payload_name="risk",
        )

from __future__ import annotations

from copy import deepcopy


class RiskDashboardEventPublisherV2:

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
        payload: dict[str, object],
        payload_name: str,
        risk_update_type: str | None = None,
    ) -> dict[str, object]:

        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                f"{payload_name} debe ser un dict."
            )

        normalized_payload = deepcopy(
            payload
        )

        if risk_update_type is not None:
            normalized_payload[
                "risk_update_type"
            ] = risk_update_type

        if self.event_bus_v2 is None:
            return {
                "published": False,
                "reason": "no_event_bus",
                "event_type": "risk_updated",
            }

        result = self.event_bus_v2.publish(
            event_type="risk_updated",
            payload=normalized_payload,
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
        ] = "risk_updated"

        return response

    def publish_risk_updated(
        self,
        *,
        risk: dict[str, object],
    ) -> dict[str, object]:

        return self._publish(
            payload=risk,
            payload_name="risk",
        )

    def publish_daily_loss_updated(
        self,
        *,
        daily_loss: dict[str, object],
    ) -> dict[str, object]:

        return self._publish(
            payload=daily_loss,
            payload_name="daily_loss",
            risk_update_type="daily_loss",
        )

    def publish_drawdown_updated(
        self,
        *,
        drawdown: dict[str, object],
    ) -> dict[str, object]:

        return self._publish(
            payload=drawdown,
            payload_name="drawdown",
            risk_update_type="drawdown",
        )

    def publish_open_risk_updated(
        self,
        *,
        open_risk: dict[str, object],
    ) -> dict[str, object]:

        return self._publish(
            payload=open_risk,
            payload_name="open_risk",
            risk_update_type="open_risk",
        )

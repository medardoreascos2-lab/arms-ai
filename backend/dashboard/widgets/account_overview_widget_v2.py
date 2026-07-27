from __future__ import annotations


class AccountOverviewWidgetV2:

    def __init__(
        self,
        *,
        dashboard_live_data_service_v2=None,
    ) -> None:

        if (
            dashboard_live_data_service_v2
            is not None
            and not callable(
                getattr(
                    dashboard_live_data_service_v2,
                    "get_snapshot",
                    None,
                )
            )
        ):
            raise TypeError(
                "dashboard_live_data_service_v2 "
                "debe implementar get_snapshot()."
            )

        self.dashboard_live_data_service_v2 = (
            dashboard_live_data_service_v2
        )

    def render(
        self,
    ) -> dict[str, object]:

        if (
            self.dashboard_live_data_service_v2
            is None
        ):
            return {
                "widget": "account_overview",
                "status": "EMPTY",
                "data": None,
            }

        snapshot = (
            self.dashboard_live_data_service_v2
            .get_snapshot()
        )

        if not isinstance(
            snapshot,
            dict,
        ):
            raise TypeError(
                "get_snapshot() debe devolver un dict."
            )

        account_overview = snapshot.get(
            "account_overview"
        )

        if account_overview is None:
            return {
                "widget": "account_overview",
                "status": "EMPTY",
                "data": None,
            }

        return {
            "widget": "account_overview",
            "status": str(
                snapshot.get(
                    "dashboard_status",
                    "READY",
                )
            ),
            "data": account_overview,
        }

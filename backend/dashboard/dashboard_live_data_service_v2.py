from __future__ import annotations

from datetime import datetime
from datetime import timezone


class DashboardLiveDataServiceV2:

    def __init__(
        self,
        *,
        dashboard_engine_v2=None,
    ) -> None:

        if (
            dashboard_engine_v2
            is not None
            and not callable(
                getattr(
                    dashboard_engine_v2,
                    "build",
                    None,
                )
            )
        ):
            raise TypeError(
                "dashboard_engine_v2 debe implementar "
                "build()."
            )

        self.dashboard_engine_v2 = (
            dashboard_engine_v2
        )

    def get_snapshot(
        self,
    ) -> dict[str, object]:

        snapshot_time = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        if (
            self.dashboard_engine_v2
            is None
        ):
            return {
                "snapshot_time":
                    snapshot_time,
                "dashboard_status":
                    "EMPTY",
                "account_state":
                    None,
                "account_overview":
                    None,
                "portfolio_summary":
                    None,
                "trade_journal_summary":
                    None,
                "performance_overview":
                    None,
                "risk_status":
                    None,
                "performance_score":
                    None,
                "analytics":
                    None,
                "breakdown":
                    None,
            }

        dashboard = (
            self.dashboard_engine_v2
            .build()
        )

        if not isinstance(
            dashboard,
            dict,
        ):
            raise TypeError(
                "dashboard_engine_v2.build() "
                "debe devolver un dict."
            )

        snapshot = dict(
            dashboard
        )

        snapshot[
            "snapshot_time"
        ] = snapshot_time

        return snapshot

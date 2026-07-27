from __future__ import annotations


class TradeJournalSummaryWidgetV2:

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
                "widget":
                    "trade_journal_summary",
                "status":
                    "EMPTY",
                "data":
                    None,
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

        trade_journal_summary = snapshot.get(
            "trade_journal_summary"
        )

        if trade_journal_summary is None:
            return {
                "widget":
                    "trade_journal_summary",
                "status":
                    "EMPTY",
                "data":
                    None,
            }

        return {
            "widget":
                "trade_journal_summary",
            "status":
                str(
                    snapshot.get(
                        "dashboard_status",
                        "READY",
                    )
                ),
            "data":
                trade_journal_summary,
        }

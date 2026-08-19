from __future__ import annotations

from backend.services.certified_market_calendar_v2 import (
    CertifiedCalendarSnapshotV2,
    CertifiedMarketCalendarV2,
)
from backend.services.market_hours_service_v2 import (
    MarketHoursServiceV2,
)
from backend.services.special_hours_snapshot_v2 import (
    CertifiedSpecialHoursSnapshotV2,
    SpecialHoursResolverV2,
)


class CertifiedMarketHoursRuntimeProviderV2:
    """
    Composition provider for certified runtime
    market-hours dependencies.

    The provider never invents calendar data.

    Without a certified calendar snapshot,
    MarketHoursServiceV2 remains fail-closed.

    Special-hours data is optional. When no certified
    special-hours snapshot exists, the special-hours
    resolver returns None and does not override the
    regular certified calendar decision.
    """

    def __init__(
        self,
        *,
        calendar_snapshot: (
            CertifiedCalendarSnapshotV2 | None
        ) = None,
        special_hours_snapshot: (
            CertifiedSpecialHoursSnapshotV2 | None
        ) = None,
    ) -> None:
        if (
            calendar_snapshot is not None
            and not isinstance(
                calendar_snapshot,
                CertifiedCalendarSnapshotV2,
            )
        ):
            raise TypeError(
                "calendar_snapshot debe ser "
                "CertifiedCalendarSnapshotV2 o None."
            )

        if (
            special_hours_snapshot is not None
            and not isinstance(
                special_hours_snapshot,
                CertifiedSpecialHoursSnapshotV2,
            )
        ):
            raise TypeError(
                "special_hours_snapshot debe ser "
                "CertifiedSpecialHoursSnapshotV2 "
                "o None."
            )

        self.calendar_snapshot = calendar_snapshot
        self.special_hours_snapshot = (
            special_hours_snapshot
        )

        self.calendar_resolver = (
            CertifiedMarketCalendarV2(
                snapshot=calendar_snapshot,
            )
        )

        self.special_hours_resolver = (
            SpecialHoursResolverV2(
                snapshot=special_hours_snapshot,
            )
        )

        self.market_hours_service = (
            MarketHoursServiceV2(
                calendar_resolver=(
                    self.calendar_resolver
                ),
                special_hours_resolver=(
                    self.special_hours_resolver.resolve
                ),
            )
        )

    def get_market_hours_service(
        self,
    ) -> MarketHoursServiceV2:
        """
        Return the single MarketHoursServiceV2
        instance owned by this provider.
        """
        return self.market_hours_service

from __future__ import annotations

from datetime import datetime

from backend.services.certified_economic_news_snapshot_v2 import (
    CertifiedEconomicNewsSnapshotV2,
)
from backend.services.economic_news_authority_v2 import (
    EconomicNewsAuthorityV2,
)


class _CoverageAwareEconomicNewsAuthorityV2:
    """
    Coverage gate around EconomicNewsAuthorityV2.

    The certified snapshot owns coverage semantics.

    Outside explicit certified coverage, evaluation is
    fail-closed.

    Inside coverage, symbol and exact-event semantics are
    delegated to EconomicNewsAuthorityV2.
    """

    def __init__(
        self,
        *,
        snapshot: CertifiedEconomicNewsSnapshotV2,
    ) -> None:
        self.snapshot = snapshot

        self._authority = EconomicNewsAuthorityV2(
            high_impact_events=(
                snapshot.high_impact_events
            ),
        )

    def is_news_blocked(
        self,
        *,
        symbol: str,
        timestamp: datetime,
    ) -> bool:
        if not self.snapshot.is_timestamp_covered(
            timestamp=timestamp,
        ):
            return True

        return self._authority.is_news_blocked(
            symbol=symbol,
            timestamp=timestamp,
        )


class EconomicNewsRuntimeProviderV2:
    """
    Runtime composition provider for certified economic-news
    authority.

    The provider never fetches, invents, expands, or infers
    economic-news data.

    Without a certified snapshot, its authority remains
    fail-closed.

    With a certified snapshot, only timestamps inside the
    explicit snapshot coverage may be evaluated as clear.
    """

    def __init__(
        self,
        *,
        snapshot: (
            CertifiedEconomicNewsSnapshotV2 | None
        ) = None,
    ) -> None:
        if (
            snapshot is not None
            and not isinstance(
                snapshot,
                CertifiedEconomicNewsSnapshotV2,
            )
        ):
            raise TypeError(
                "snapshot must be "
                "CertifiedEconomicNewsSnapshotV2 "
                "or None"
            )

        self.snapshot = snapshot

        if snapshot is None:
            self._economic_news_authority = (
                EconomicNewsAuthorityV2()
            )
        else:
            self._economic_news_authority = (
                _CoverageAwareEconomicNewsAuthorityV2(
                    snapshot=snapshot,
                )
            )

    def is_timestamp_covered(
        self,
        *,
        timestamp: datetime,
    ) -> bool:
        if self.snapshot is None:
            return False

        return self.snapshot.is_timestamp_covered(
            timestamp=timestamp,
        )

    def get_economic_news_authority(
        self,
    ):
        return self._economic_news_authority

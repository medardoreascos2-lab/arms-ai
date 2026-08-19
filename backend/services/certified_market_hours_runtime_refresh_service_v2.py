from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.services.certified_market_hours_data_lifecycle_v2 import (
    CertifiedMarketHoursDataLifecycleV2,
)
from backend.services.certified_market_hours_runtime_provider_v2 import (
    CertifiedMarketHoursRuntimeProviderV2,
)
from backend.services.market_hours_service_v2 import (
    MarketHoursServiceV2,
)


class CertifiedMarketHoursRuntimeRefreshServiceV2:
    """
    Coordinates transactional replacement of certified market-hours
    runtime state.

    The lifecycle owns snapshot validation and provider activation.
    This service publishes the newly activated provider/service into
    application state only after activation succeeds.

    If activation fails, application runtime state remains unchanged.
    """

    def __init__(
        self,
        *,
        app_state: Any,
        lifecycle: CertifiedMarketHoursDataLifecycleV2,
    ) -> None:
        if app_state is None:
            raise ValueError(
                "app_state es obligatorio."
            )

        if not isinstance(
            lifecycle,
            CertifiedMarketHoursDataLifecycleV2,
        ):
            raise TypeError(
                "lifecycle debe ser "
                "CertifiedMarketHoursDataLifecycleV2."
            )

        self.app_state = app_state
        self.lifecycle = lifecycle

    def refresh_from_file(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        lifecycle_checkpoint = (
            self.lifecycle.create_runtime_checkpoint()
        )

        previous_provider = getattr(
            self.app_state,
            "market_hours_runtime_provider_v2",
            None,
        )
        previous_service = getattr(
            self.app_state,
            "market_hours_service_v2",
            None,
        )

        try:
            activation_report = (
                self.lifecycle.activate_from_file(
                    file_path=file_path,
                )
            )

            provider = (
                self.lifecycle.get_active_provider()
            )

            if not isinstance(
                provider,
                CertifiedMarketHoursRuntimeProviderV2,
            ):
                raise RuntimeError(
                    "certified market hours refresh "
                    "did not produce a runtime provider"
                )

            service = (
                provider.get_market_hours_service()
            )

            if not isinstance(
                service,
                MarketHoursServiceV2,
            ):
                raise RuntimeError(
                    "certified market hours refresh "
                    "did not produce MarketHoursServiceV2"
                )

            self.app_state.market_hours_runtime_provider_v2 = (
                provider
            )
            self.app_state.market_hours_service_v2 = (
                service
            )

            return {
                **activation_report,
                "runtime_published": True,
            }

        except Exception:
            self.lifecycle.restore_runtime_checkpoint(
                checkpoint=lifecycle_checkpoint,
            )
            self.app_state.market_hours_runtime_provider_v2 = (
                previous_provider
            )
            self.app_state.market_hours_service_v2 = (
                previous_service
            )
            raise

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.services.certified_economic_news_data_lifecycle_v2 import (
    CertifiedEconomicNewsDataLifecycleV2,
)
from backend.services.economic_news_runtime_provider_v2 import (
    EconomicNewsRuntimeProviderV2,
)


class CertifiedEconomicNewsRuntimeRefreshServiceV2:
    """Atomically activate certified news and republish its runtime authority."""

    def __init__(
        self,
        *,
        app_state: Any,
        lifecycle: CertifiedEconomicNewsDataLifecycleV2,
    ) -> None:
        if app_state is None:
            raise ValueError("app_state es obligatorio.")
        if not isinstance(lifecycle, CertifiedEconomicNewsDataLifecycleV2):
            raise TypeError(
                "lifecycle debe ser CertifiedEconomicNewsDataLifecycleV2."
            )
        self.app_state = app_state
        self.lifecycle = lifecycle

    def refresh_from_file(self, *, file_path: str | Path) -> dict[str, object]:
        checkpoint = self.lifecycle.create_runtime_checkpoint()
        previous_provider = getattr(
            self.app_state, "economic_news_runtime_provider_v2", None
        )
        previous_authority = getattr(
            self.app_state, "economic_news_authority_v2", None
        )
        try:
            report = self.lifecycle.activate_from_file(file_path=file_path)
            provider = self.lifecycle.get_active_provider()
            if not isinstance(provider, EconomicNewsRuntimeProviderV2):
                raise RuntimeError(
                    "certified economic news refresh did not produce a runtime provider"
                )
            authority = provider.get_economic_news_authority()
            self.app_state.economic_news_runtime_provider_v2 = provider
            self.app_state.economic_news_authority_v2 = authority
            return {**report, "runtime_published": True}
        except Exception:
            self.lifecycle.restore_runtime_checkpoint(checkpoint=checkpoint)
            self.app_state.economic_news_runtime_provider_v2 = previous_provider
            self.app_state.economic_news_authority_v2 = previous_authority
            raise

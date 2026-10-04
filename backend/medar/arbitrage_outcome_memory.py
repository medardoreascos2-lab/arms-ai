"""Session-only arbitrage observations; net edge includes every stated cost."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import has_secret_like_content


class PaperResultMode(str, Enum):
    NO_PAPER_FILL = "NO_PAPER_FILL"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    UNVERIFIED_EXTERNAL = "UNVERIFIED_EXTERNAL"


@dataclass(frozen=True)
class ArbitrageOutcomeMemory:
    tenant_id: str
    owner_id: str
    session_id: str
    source_reference: str
    dataset_reference: str
    opportunity_reference: str
    measurement_currency: str
    gross_spread: Decimal
    fee_cost: Decimal
    slippage_cost: Decimal
    network_cost: Decimal
    liquidity_cost: Decimal
    paper_result_mode: PaperResultMode
    paper_result: str = field(repr=False)
    observed_at: datetime
    domain: DurableMemoryDomain = DurableMemoryDomain.CRYPTO_ARBITRAGE
    sensitivity: DurableSensitivity = DurableSensitivity.SENSITIVE
    session_only: bool = True
    analysis_only: bool = True
    exchange_execution_authority: bool = False
    paper_execution_authority: bool = False
    live_execution_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "session_id", "source_reference", "dataset_reference", "opportunity_reference", "measurement_currency"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be a bounded explicit reference")
        for name in ("gross_spread", "fee_cost", "slippage_cost", "network_cost", "liquidity_cost"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError(f"{name} must be a finite nonnegative Decimal")
        if not isinstance(self.paper_result_mode, PaperResultMode):
            raise TypeError("paper result evidence mode must be explicit")
        if not isinstance(self.paper_result, str) or not self.paper_result.strip() or len(self.paper_result) > 1024:
            raise ValueError("paper result must be bounded explicit text")
        if has_secret_like_content(self.paper_result):
            raise PermissionError("secret-like paper result is not retained")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observation time must be timezone-aware")
        if self.domain is not DurableMemoryDomain.CRYPTO_ARBITRAGE or self.sensitivity is not DurableSensitivity.SENSITIVE:
            raise ValueError("arbitrage outcome domain and sensitivity cannot be weakened")
        if not self.session_only or not self.analysis_only or self.exchange_execution_authority or self.paper_execution_authority or self.live_execution_authority:
            raise ValueError("arbitrage outcome cannot authorize execution")

    @property
    def net_edge(self) -> Decimal:
        return self.gross_spread - self.fee_cost - self.slippage_cost - self.network_cost - self.liquidity_cost

    @property
    def profitable_on_stated_costs(self) -> bool:
        return self.net_edge > 0

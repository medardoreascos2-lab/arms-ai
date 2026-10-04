"""Explicit observed-vs-hypothetical shadow performance comparison."""

from dataclasses import dataclass
from decimal import Decimal

from backend.financial.shadow_counterfactual import CounterfactualResult
from backend.financial.shadow_decision import ShadowDecisionPair
from backend.financial.trade_record import TradeOrigin


@dataclass(frozen=True)
class UserShadowComparison:
    trade_record_id: str
    asset_id: str
    user_result_pnl: Decimal | None
    user_origin: TradeOrigin
    shadow_result_pnl: Decimal | None
    shadow_status: str
    user_plus_medar_filter_pnl: Decimal | None
    shadow_label: str = "HYPOTHETICAL_COUNTERFACTUAL_NOT_EXECUTED"
    filter_label: str = "HYPOTHETICAL_FILTER_NOT_EXECUTED"
    execution_authority: bool = False

    def __post_init__(self) -> None:
        if self.execution_authority or self.shadow_label != "HYPOTHETICAL_COUNTERFACTUAL_NOT_EXECUTED" or self.filter_label != "HYPOTHETICAL_FILTER_NOT_EXECUTED":
            raise ValueError("shadow comparison cannot claim execution")


def compare_user_shadow(
    pair: ShadowDecisionPair, counterfactual: CounterfactualResult,
) -> UserShadowComparison:
    if pair.user_decision.record_id != counterfactual.trade_record_id:
        raise ValueError("counterfactual trade identity mismatch")
    would_trade = pair.medar_shadow_decision.would_trade
    if would_trade is False:
        filtered = Decimal(0)
    elif would_trade is True:
        filtered = pair.user_decision.result_pnl
    else:
        filtered = None
    return UserShadowComparison(
        pair.user_decision.record_id,
        pair.user_decision.asset_id,
        pair.user_decision.result_pnl,
        pair.user_decision.origin,
        counterfactual.net_pnl_quote,
        counterfactual.status.value,
        filtered,
    )

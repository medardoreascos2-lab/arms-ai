"""F106C: observed PAPER and hypothetical outcomes remain separate."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.financial.shadow_comparison import compare_user_shadow
from backend.financial.shadow_counterfactual import (
    CounterfactualResult, CounterfactualStatus,
)
from backend.financial.shadow_decision import ShadowDecision, ShadowDecisionPair
from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin, TradeSide

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_user_paper_shadow_and_filtered_results_have_distinct_labels():
    trade = FinancialTradeRecord(
        "synthetic:t1", "synthetic:journal", TradeOrigin.PAPER_OBSERVED,
        "CME:MNQ:2026-12", TradeSide.LONG, Decimal("100"), Decimal("101"),
        Decimal("1"), Decimal("99"), Decimal("102"), NOW, NOW + timedelta(minutes=1),
        "setup-a", "TREND", (), Decimal("2"), Decimal("0"), Decimal("0"),
    )
    shadow = ShadowDecision("synthetic:t1", trade.asset_id, NOW, False, None, None, None, None,
                            "risk gate", None, ())
    counterfactual = CounterfactualResult(
        "synthetic:t1", CounterfactualStatus.NO_ENTRY_IN_PATH, None, None, None,
        Decimal("0"), "synthetic:dataset", ("SHADOW_DECLINED_TRADE",),
    )
    result = compare_user_shadow(ShadowDecisionPair(trade, shadow), counterfactual)
    assert result.user_result_pnl == Decimal("2")
    assert result.user_origin is TradeOrigin.PAPER_OBSERVED
    assert result.shadow_result_pnl == Decimal("0")
    assert result.user_plus_medar_filter_pnl == Decimal("0")
    assert result.shadow_label.startswith("HYPOTHETICAL")
    assert result.filter_label.startswith("HYPOTHETICAL")
    assert not result.execution_authority

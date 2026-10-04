"""F106B: shadow result uses only future historical bars and labels assumptions."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.shadow_counterfactual import (
    CounterfactualStatus, HistoricalPriceBar, compute_counterfactual,
)
from backend.financial.shadow_decision import ShadowDecision
from backend.financial.trade_record import TradeSide

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
DECISION = ShadowDecision(
    "synthetic:t1", "CME:NQ:2026-12", NOW, True, TradeSide.LONG,
    Decimal("100"), Decimal("99"), Decimal("102"), "synthetic setup",
    Decimal("0.8"), ("synthetic:signal",),
)


def bar(start, low, high):
    return HistoricalPriceBar(start, start + timedelta(minutes=1),
                              Decimal(low), Decimal(high), "synthetic:bars")


def test_ambiguous_same_bar_uses_stop_first_and_explicit_costs():
    result = compute_counterfactual(
        DECISION, (bar(NOW, "99", "102"),), "synthetic:dataset-1",
        Decimal("1"), Decimal("20"), Decimal("1"), Decimal("1"),
    )
    assert result.status is CounterfactualStatus.RESOLVED
    assert result.exit_price == Decimal("99")
    assert result.net_pnl_quote == Decimal("-22")
    assert result.assumptions == ("STOP_FIRST_ON_AMBIGUOUS_BAR",)
    assert result.labels == ("HYPOTHETICAL", "COUNTERFACTUAL", "NOT_EXECUTED")
    assert not result.execution_authority


def test_path_before_decision_is_rejected():
    with pytest.raises(ValueError, match="overlaps"):
        compute_counterfactual(
            DECISION, (bar(NOW - timedelta(minutes=1), "99", "102"),),
            "synthetic:dataset-1", Decimal("1"), Decimal("20"), Decimal("0"), Decimal("0"),
        )


def test_missing_path_stays_incomplete():
    result = compute_counterfactual(DECISION, (), "synthetic:dataset-1",
                                    Decimal("1"), Decimal("20"), Decimal("0"), Decimal("0"))
    assert result.status is CounterfactualStatus.INCOMPLETE_DATA
    assert result.net_pnl_quote is None


def test_gap_through_stop_does_not_invent_exit_fill_price():
    result = compute_counterfactual(
        DECISION, (bar(NOW, "100", "101"), bar(NOW + timedelta(minutes=1), "97", "98")),
        "synthetic:dataset-1", Decimal("1"), Decimal("20"), Decimal("0"), Decimal("0"),
    )
    assert result.status is CounterfactualStatus.INCOMPLETE_DATA
    assert result.net_pnl_quote is None
    assert result.assumptions == ("GAP_THROUGH_EXIT_FILL_UNKNOWN",)

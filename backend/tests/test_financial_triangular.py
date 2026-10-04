"""F104C: triangular analysis compounds fees and slippage without execution."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.triangular import ConversionLeg, analyze_triangular

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def legs():
    return (
        ConversionLeg("COINBASE", "A", "B", Decimal("2"), Decimal("0.01"),
                      Decimal("0.01"), Decimal("100"), NOW, "synthetic:ab"),
        ConversionLeg("COINBASE", "B", "C", Decimal("2"), Decimal("0.01"),
                      Decimal("0.01"), Decimal("100"), NOW, "synthetic:bc"),
        ConversionLeg("COINBASE", "C", "A", Decimal("0.26"), Decimal("0.01"),
                      Decimal("0.01"), Decimal("100"), NOW, "synthetic:ca"),
    )


def test_fees_and_slippage_can_reverse_gross_edge():
    result = analyze_triangular(legs(), Decimal("10"), NOW, timedelta(seconds=30))
    assert result.gross_end_amount == Decimal("10.40")
    assert result.net_edge < 0
    assert result.sources == ("synthetic:ab", "synthetic:bc", "synthetic:ca")
    assert result.analysis_only and not hasattr(result, "execute")


def test_mismatched_path_rejected():
    path = list(legs())
    path[2] = ConversionLeg("COINBASE", "X", "A", Decimal("0.26"), Decimal("0.01"),
                            Decimal("0.01"), Decimal("100"), NOW, "synthetic:xa")
    with pytest.raises(ValueError, match="path"):
        analyze_triangular(tuple(path), Decimal("10"), NOW, timedelta(seconds=30))

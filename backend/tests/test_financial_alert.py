"""F110A: financial alerts are sourced, advisory and nonexecuting."""

from datetime import datetime, timezone

import pytest

from backend.financial.alert import AlertCategory, AlertPriority, FinancialAlert

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_alert_priority_and_category_are_explicit():
    alert = FinancialAlert("synthetic:a1", AlertCategory.PORTFOLIO, AlertPriority.WATCH,
                           "concentration high", "synthetic:risk-1", NOW)
    assert alert.advisory_only
    assert not alert.execution_authority
    assert not hasattr(alert, "submit_order")


def test_alert_cannot_grant_execution():
    with pytest.raises(ValueError, match="execution"):
        FinancialAlert("synthetic:a1", AlertCategory.RISK, AlertPriority.CRITICAL,
                       "risk", "synthetic:risk-1", NOW, execution_authority=True)

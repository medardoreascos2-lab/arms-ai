from copy import deepcopy

from backend.risk.risk_event_analytics_v2 import (
    RiskEventAnalyticsV2,
)


def test_empty_events_return_empty_summary():
    analytics = RiskEventAnalyticsV2()

    result = analytics.summarize([])

    assert result == {
        "total_events": 0,
        "decision_summary": {
            "approved": 0,
            "blocked": 0,
            "unknown": 0,
            "decision_total": 0,
            "approval_rate_percent": None,
            "block_rate_percent": None,
        },
        "by_event_type": {},
        "by_symbol": {},
        "by_reason": {},
    }


def test_summarizes_decisions_event_types_symbols_and_reasons():
    analytics = RiskEventAnalyticsV2()

    events = [
        {
            "event_type": "risk_approved",
            "symbol": "NQ",
            "approved": True,
        },
        {
            "event_type": "risk_blocked",
            "symbol": "NQ",
            "approved": False,
            "reason": "daily_loss_limit",
        },
        {
            "event_type": "risk_blocked",
            "symbol": "ES",
            "approved": False,
            "blocking_reasons": [
                "maximum_contracts",
                "daily_loss_limit",
            ],
        },
    ]

    result = analytics.summarize(events)

    assert result["total_events"] == 3

    assert result["decision_summary"] == {
        "approved": 1,
        "blocked": 2,
        "unknown": 0,
        "decision_total": 3,
        "approval_rate_percent": 33.33,
        "block_rate_percent": 66.67,
    }

    assert result["by_event_type"] == {
        "risk_blocked": 2,
        "risk_approved": 1,
    }

    assert result["by_symbol"] == {
        "NQ": 2,
        "ES": 1,
    }

    assert result["by_reason"] == {
        "daily_loss_limit": 2,
        "maximum_contracts": 1,
    }


def test_extracts_nested_risk_fields():
    analytics = RiskEventAnalyticsV2()

    events = [
        {
            "event_type": "execution_risk",
            "signal": {
                "symbol": "MNQ",
            },
            "risk_evaluation": {
                "approved": False,
                "blocking_reasons": [
                    "risk_limit",
                ],
            },
        }
    ]

    result = analytics.summarize(events)

    assert result["by_symbol"] == {
        "MNQ": 1,
    }

    assert result["decision_summary"]["blocked"] == 1

    assert result["by_reason"] == {
        "risk_limit": 1,
    }


def test_event_type_can_supply_decision_when_boolean_missing():
    analytics = RiskEventAnalyticsV2()

    result = analytics.summarize(
        [
            {
                "event_type": "execution_blocked",
            },
            {
                "event_type": "execution_approved",
            },
            {
                "event_type": "risk_observed",
            },
        ]
    )

    assert result["decision_summary"] == {
        "approved": 1,
        "blocked": 1,
        "unknown": 1,
        "decision_total": 2,
        "approval_rate_percent": 50.0,
        "block_rate_percent": 50.0,
    }


def test_duplicate_reason_inside_one_event_is_counted_once():
    analytics = RiskEventAnalyticsV2()

    result = analytics.summarize(
        [
            {
                "reason": "daily_loss_limit",
                "blocking_reasons": [
                    "daily_loss_limit",
                ],
            }
        ]
    )

    assert result["by_reason"] == {
        "daily_loss_limit": 1,
    }


def test_summary_does_not_mutate_source_events():
    analytics = RiskEventAnalyticsV2()

    events = [
        {
            "event_type": "risk_blocked",
            "symbol": "NQ",
            "blocking_reasons": [
                "daily_loss_limit",
            ],
        }
    ]

    original = deepcopy(events)

    analytics.summarize(events)

    assert events == original


def test_invalid_non_dict_items_are_ignored():
    analytics = RiskEventAnalyticsV2()

    result = analytics.summarize(
        [
            None,
            "invalid",
            123,
            {
                "event_type": "risk_approved",
                "approved": True,
            },
        ]
    )

    assert result["total_events"] == 1
    assert result["decision_summary"]["approved"] == 1


def test_blank_values_are_not_added_to_breakdowns():
    analytics = RiskEventAnalyticsV2()

    result = analytics.summarize(
        [
            {
                "event_type": " ",
                "symbol": "",
                "reason": "   ",
            }
        ]
    )

    assert result["total_events"] == 1
    assert result["by_event_type"] == {}
    assert result["by_symbol"] == {}
    assert result["by_reason"] == {}


def test_count_order_is_deterministic():
    analytics = RiskEventAnalyticsV2()

    result = analytics.summarize(
        [
            {"symbol": "ES"},
            {"symbol": "NQ"},
            {"symbol": "NQ"},
            {"symbol": "YM"},
            {"symbol": "ES"},
        ]
    )

    assert list(result["by_symbol"]) == [
        "ES",
        "NQ",
        "YM",
    ]

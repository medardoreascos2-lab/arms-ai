from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.execution.execution_decision_engine_v2 import (
    ExecutionDecisionEngineV2,
)
from backend.execution.trade_validator_v2 import TradeValidatorV2
from backend.services.price_feed_service_v2 import PriceFeedServiceV2


class MonitorSpy:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def process_price(
        self,
        *,
        symbol: str,
        current_price: float,
    ) -> dict[str, object]:
        payload = {
            "symbol": symbol,
            "current_price": current_price,
        }
        self.calls.append(payload)
        return {
            "processed": True,
            **payload,
        }


def build_valid_plan() -> dict[str, object]:
    return {
        "approved": True,
        "status": "ACTIVE",
        "direction": "LONG",
        "entry_price": 20000.0,
        "stop_loss": 19990.0,
        "take_profit": 20020.0,
        "risk_points": 10.0,
        "reward_points": 20.0,
        "reward_risk_ratio": 2.0,
        "contracts": 1,
        "probability": 1.0,
        "confluence_score": 1.0,
        "grade": "A+",
    }


def build_validator(
    *,
    maximum_signal_age_seconds: int = 30,
) -> TradeValidatorV2:
    return TradeValidatorV2(
        minimum_reward_risk_ratio=2.0,
        minimum_stop_points=1.0,
        maximum_stop_points=100.0,
        maximum_spread_points=5.0,
        minimum_atr_points=1.0,
        maximum_signal_age_seconds=maximum_signal_age_seconds,
    )


def validate_plan(
    validator: TradeValidatorV2,
    *,
    session_allowed: bool = True,
    news_blocked: bool = False,
    signal_age_seconds: int = 5,
) -> dict[str, object]:
    return validator.validate(
        trade_plan=build_valid_plan(),
        spread_points=1.0,
        atr_points=20.0,
        session_allowed=session_allowed,
        news_blocked=news_blocked,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=signal_age_seconds,
    )


def build_decision_engine(
    *,
    minimum_probability: float,
    minimum_confluence_score: float,
) -> ExecutionDecisionEngineV2:
    return ExecutionDecisionEngineV2(
        minimum_probability=minimum_probability,
        minimum_confluence_score=minimum_confluence_score,
    )


def evaluate_long(
    engine: ExecutionDecisionEngineV2,
    *,
    probability: float,
    confluence_score: float,
    news_blocked: bool = False,
) -> dict[str, object]:
    return engine.evaluate(
        signal_direction="LONG",
        probability=probability,
        confluence_score=confluence_score,
        smart_money_direction="BULLISH",
        market_regime="TREND_UP",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=1,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=news_blocked,
    )


def test_trade_validator_rejects_stale_signal():
    validator = build_validator(
        maximum_signal_age_seconds=30,
    )

    result = validate_plan(
        validator,
        signal_age_seconds=300,
    )

    assert result["approved"] is False
    assert "signal_expired" in result["blocking_reasons"]


def test_trade_validator_accepts_fresh_signal_control():
    validator = build_validator(
        maximum_signal_age_seconds=30,
    )

    result = validate_plan(
        validator,
        signal_age_seconds=5,
    )

    assert result["approved"] is True


def test_trade_validator_rejects_closed_session():
    validator = build_validator()

    result = validate_plan(
        validator,
        session_allowed=False,
    )

    assert result["approved"] is False
    assert "session_not_allowed" in result["blocking_reasons"]


def test_trade_validator_rejects_news_block():
    validator = build_validator()

    result = validate_plan(
        validator,
        news_blocked=True,
    )

    assert result["approved"] is False
    assert "high_impact_news" in result["blocking_reasons"]


def test_execution_decision_respects_probability_threshold():
    engine = build_decision_engine(
        minimum_probability=0.99,
        minimum_confluence_score=0.80,
    )

    result = evaluate_long(
        engine,
        probability=0.95,
        confluence_score=1.0,
    )

    assert result["approved"] is False
    assert result["decision"] == "WAIT"
    assert (
        "probability_below_threshold"
        in result["waiting_reasons"]
    )


def test_execution_decision_respects_confluence_threshold():
    engine = build_decision_engine(
        minimum_probability=0.80,
        minimum_confluence_score=0.99,
    )

    result = evaluate_long(
        engine,
        probability=1.0,
        confluence_score=0.95,
    )

    assert result["approved"] is False
    assert result["decision"] == "WAIT"
    assert (
        "confluence_below_threshold"
        in result["waiting_reasons"]
    )


def test_execution_decision_rejects_news():
    engine = build_decision_engine(
        minimum_probability=0.80,
        minimum_confluence_score=0.80,
    )

    result = evaluate_long(
        engine,
        probability=1.0,
        confluence_score=1.0,
        news_blocked=True,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "high_impact_news"
        in result["blocking_reasons"]
    )


def test_price_feed_contract_requires_authoritative_timestamp():
    signature_source = Path(
        "backend/services/price_feed_service_v2.py"
    ).read_text(encoding="utf-8")

    assert "timestamp:" in signature_source
    assert "maximum_age_seconds" in signature_source


def test_price_feed_rejects_stale_operational_price_before_monitor():
    monitor = MonitorSpy()
    feed = PriceFeedServiceV2(
        live_position_monitor_v2=monitor,
    )

    now = datetime.now(timezone.utc)

    with pytest.raises((ValueError, RuntimeError)):
        feed.process_price(
            symbol="MNQ",
            current_price=20000.0,
            source="MARKET_WEBHOOK",
            timestamp=now - timedelta(minutes=5),
            current_timestamp=now,
            maximum_age_seconds=30,
        )

    assert monitor.calls == []


def test_price_feed_rejects_out_of_order_operational_price():
    monitor = MonitorSpy()
    feed = PriceFeedServiceV2(
        live_position_monitor_v2=monitor,
    )

    now = datetime.now(timezone.utc)

    first = feed.process_price(
        symbol="MNQ",
        current_price=20000.0,
        source="MARKET_WEBHOOK",
        timestamp=now - timedelta(seconds=2),
        current_timestamp=now,
        maximum_age_seconds=30,
    )

    assert first["processed"] is True
    assert len(monitor.calls) == 1

    with pytest.raises((ValueError, RuntimeError)):
        feed.process_price(
            symbol="MNQ",
            current_price=19990.0,
            source="MARKET_WEBHOOK",
            timestamp=now - timedelta(seconds=3),
            current_timestamp=now,
            maximum_age_seconds=30,
        )

    assert len(monitor.calls) == 1


def test_price_feed_accepts_fresh_monotonic_operational_price_control():
    monitor = MonitorSpy()
    feed = PriceFeedServiceV2(
        live_position_monitor_v2=monitor,
    )

    now = datetime.now(timezone.utc)

    result = feed.process_price(
        symbol="MNQ",
        current_price=20000.0,
        source="MARKET_WEBHOOK",
        timestamp=now - timedelta(seconds=1),
        current_timestamp=now,
        maximum_age_seconds=30,
    )

    assert result["processed"] is True
    assert len(monitor.calls) == 1


def test_debug_price_route_not_mounted_in_normal_router():
    source = Path(
        "backend/api/routers/intelligence_decision_api_v3.py"
    ).read_text(encoding="utf-8")

    assert '"/monitor-price-debug"' not in source


def test_app_wires_trade_validator():
    source = Path(
        "backend/api/app.py"
    ).read_text(encoding="utf-8")

    assert "TradeValidatorV2" in source
    assert "maximum_signal_age_seconds" in source
    assert "app.state.trade_validator_v2" in source


def test_app_wires_execution_decision_policy():
    source = Path(
        "backend/api/app.py"
    ).read_text(encoding="utf-8")

    assert "ExecutionDecisionEngineV2" in source
    assert "minimum_a_plus_probability" in source
    assert "minimum_a_plus_confluence_score" in source
    assert "app.state.execution_decision_engine_v2" in source


def test_app_wires_order_validation():
    source = Path(
        "backend/api/app.py"
    ).read_text(encoding="utf-8")

    assert "OrderValidationEngineV2" in source
    assert "order_validation_engine_v2" in source

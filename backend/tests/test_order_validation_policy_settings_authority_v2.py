from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.api.app import create_app
from backend.config.api_settings import APISettings


def _configure_required_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reward_risk: str = "2.75",
    minimum_stop: str = "7.0",
    maximum_stop: str = "37.0",
) -> None:
    monkeypatch.setenv(
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS",
        "5.0",
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_REWARD_RISK_RATIO",
        reward_risk,
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_STOP_POINTS",
        minimum_stop,
    )
    monkeypatch.setenv(
        "ARMS_MAXIMUM_STOP_POINTS",
        maximum_stop,
    )
    monkeypatch.setenv(
        "ARMS_MAXIMUM_SPREAD_POINTS",
        "1.0",
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_ATR_POINTS",
        "3.0",
    )
    monkeypatch.setenv(
        "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS",
        "30",
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_A_PLUS_PROBABILITY",
        "0.80",
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE",
        "0.80",
    )


def _app_tree() -> ast.Module:
    return ast.parse(
        Path(
            "backend/api/app.py"
        ).read_text(
            encoding="utf-8"
        )
    )


def _order_validation_call() -> ast.Call:
    tree = _app_tree()

    calls = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(
                node.func
            ).split(".")[-1]
        except Exception:
            continue

        if name == "OrderValidationEngineV2":
            calls.append(node)

    assert len(calls) == 1

    return calls[0]


def test_order_validation_engine_uses_settings_authority_static() -> None:
    call = _order_validation_call()

    keyword_values = {
        keyword.arg:
            ast.unparse(keyword.value)
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert {
        "minimum_reward_risk_ratio":
            keyword_values.get(
                "minimum_reward_risk_ratio"
            ),
        "minimum_stop_points":
            keyword_values.get(
                "minimum_stop_points"
            ),
        "maximum_stop_points":
            keyword_values.get(
                "maximum_stop_points"
            ),
    } == {
        "minimum_reward_risk_ratio":
            "settings.minimum_reward_risk_ratio",
        "minimum_stop_points":
            "settings.minimum_stop_points",
        "maximum_stop_points":
            "settings.maximum_stop_points",
    }


def test_order_validation_engine_has_no_rr_stop_literals() -> None:
    call = _order_validation_call()

    matching = [
        keyword
        for keyword in call.keywords
        if keyword.arg in {
            "minimum_reward_risk_ratio",
            "minimum_stop_points",
            "maximum_stop_points",
        }
    ]

    assert len(matching) == 3

    for keyword in matching:
        assert not isinstance(
            keyword.value,
            ast.Constant,
        ), (
            f"{keyword.arg} todavía posee "
            "autoridad literal."
        )


def test_runtime_order_validator_matches_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_environment(
        monkeypatch,
        reward_risk="2.75",
        minimum_stop="7.0",
        maximum_stop="37.0",
    )

    settings = APISettings()

    app = create_app(
        settings=settings
    )

    lifecycle = (
        app.state.trade_lifecycle_service_v2
    )

    order_validator = (
        lifecycle.order_validation_engine_v2
    )

    assert (
        order_validator.minimum_reward_risk_ratio
        == settings.minimum_reward_risk_ratio
        == pytest.approx(2.75)
    )

    assert (
        order_validator.minimum_stop_points
        == settings.minimum_stop_points
        == pytest.approx(7.0)
    )

    assert (
        order_validator.maximum_stop_points
        == settings.maximum_stop_points
        == pytest.approx(37.0)
    )


def test_trade_and_order_validators_share_runtime_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_environment(
        monkeypatch,
        reward_risk="2.75",
        minimum_stop="7.0",
        maximum_stop="37.0",
    )

    settings = APISettings()

    app = create_app(
        settings=settings
    )

    trade_validator = (
        app.state.trade_validator_v2
    )

    order_validator = (
        app.state
        .trade_lifecycle_service_v2
        .order_validation_engine_v2
    )

    assert (
        trade_validator.minimum_reward_risk_ratio
        == order_validator.minimum_reward_risk_ratio
        == settings.minimum_reward_risk_ratio
    )

    assert (
        trade_validator.minimum_stop_points
        == order_validator.minimum_stop_points
        == settings.minimum_stop_points
    )

    assert (
        trade_validator.maximum_stop_points
        == order_validator.maximum_stop_points
        == settings.maximum_stop_points
    )


def test_same_trade_geometry_cannot_bypass_certified_order_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_environment(
        monkeypatch,
        reward_risk="2.75",
        minimum_stop="7.0",
        maximum_stop="37.0",
    )

    settings = APISettings()

    app = create_app(
        settings=settings
    )

    trade_validator = (
        app.state.trade_validator_v2
    )

    order_validator = (
        app.state
        .trade_lifecycle_service_v2
        .order_validation_engine_v2
    )

    trade_result = trade_validator.validate(
        trade_plan={
            "approved": True,
            "status": "ACTIVE",
            "reward_risk_ratio": 2.5,
            "risk_points": 5.0,
        },
        spread_points=0.5,
        atr_points=10.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=0,
    )

    order_result = order_validator.validate(
        prepared_order={
            "approved": True,
            "status": "READY_TO_SUBMIT",
            "decision": "SUBMIT_ORDER",
            "symbol": "NQ",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 1,
            "entry_price": 100.0,
            "stop_loss": 95.0,
            "take_profit": 112.5,
            "limit_price": None,
        },
        market_is_open=True,
        open_symbols=set(),
    )

    assert trade_result["approved"] is False
    assert order_result["approved"] is False

    assert (
        "reward_risk_below_minimum"
        in trade_result["blocking_reasons"]
    )
    assert (
        "stop_distance_too_small"
        in trade_result["blocking_reasons"]
    )

    assert (
        "reward_risk_below_minimum"
        in order_result["blocking_reasons"]
    )
    assert (
        "stop_distance_below_minimum"
        in order_result["blocking_reasons"]
    )

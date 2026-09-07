from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.api.app import create_app
from backend.config.api_settings import APISettings


def _configure_required_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reward_risk_ratio: str = "2.5",
) -> None:
    monkeypatch.setenv(
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS",
        "5.0",
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_REWARD_RISK_RATIO",
        reward_risk_ratio,
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_STOP_POINTS",
        "2.0",
    )
    monkeypatch.setenv(
        "ARMS_MAXIMUM_STOP_POINTS",
        "50.0",
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


def _trade_planner_calls() -> list[ast.Call]:
    path = Path(
        "backend/api/app.py"
    )
    source = path.read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)

    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        try:
            name = ast.unparse(
                node.func
            )
        except Exception:
            continue

        if name == "TradePlannerV2":
            calls.append(node)

    return calls


def test_production_trade_planner_uses_settings_reward_risk_authority() -> None:
    calls = _trade_planner_calls()

    assert len(calls) == 1

    call = calls[0]

    actual = {
        keyword.arg:
            ast.unparse(keyword.value)
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert (
        actual.get(
            "minimum_reward_risk_ratio"
        )
        == "settings.minimum_reward_risk_ratio"
    )


def test_production_trade_planner_has_no_reward_risk_literal() -> None:
    calls = _trade_planner_calls()

    assert len(calls) == 1

    call = calls[0]

    matching = [
        keyword
        for keyword in call.keywords
        if (
            keyword.arg
            == "minimum_reward_risk_ratio"
        )
    ]

    assert len(matching) == 1

    assert not isinstance(
        matching[0].value,
        ast.Constant,
    ), (
        "TradePlannerV2 todavía usa "
        "minimum_reward_risk_ratio "
        "como literal productivo."
    )


def test_runtime_trade_planner_and_validator_share_reward_risk_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_environment(
        monkeypatch,
        reward_risk_ratio="2.5",
    )

    settings = APISettings()

    app = create_app(
        settings=settings,
    )

    planner = (
        app.state.trade_planner_v2
    )
    validator = (
        app.state.trade_validator_v2
    )

    assert (
        planner.minimum_reward_risk_ratio
        == pytest.approx(2.5)
    )
    assert (
        validator.minimum_reward_risk_ratio
        == pytest.approx(2.5)
    )
    assert (
        planner.minimum_reward_risk_ratio
        == validator.minimum_reward_risk_ratio
        == settings.minimum_reward_risk_ratio
    )


def test_runtime_trade_planner_respects_configured_higher_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_environment(
        monkeypatch,
        reward_risk_ratio="2.5",
    )

    settings = APISettings()

    app = create_app(
        settings=settings,
    )

    planner = (
        app.state.trade_planner_v2
    )

    with pytest.raises(
        ValueError,
        match="reward_risk_ratio",
    ):
        planner.build(
            decision="EXECUTE_LONG",
            current_price=100.0,
            stop_loss=95.0,
            contracts=1,
            probability=0.90,
            confluence_score=0.90,
            grade="A+",
            reward_risk_ratio=2.0,
        )


def test_runtime_trade_planner_builds_default_target_from_configured_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_environment(
        monkeypatch,
        reward_risk_ratio="2.5",
    )

    settings = APISettings()

    app = create_app(
        settings=settings,
    )

    planner = (
        app.state.trade_planner_v2
    )

    result = planner.build(
        decision="EXECUTE_LONG",
        current_price=100.0,
        stop_loss=96.0,
        contracts=1,
        probability=0.90,
        confluence_score=0.90,
        grade="A+",
    )

    assert result["approved"] is True
    assert (
        result["reward_risk_ratio"]
        == pytest.approx(2.5)
    )
    assert (
        result["risk_points"]
        == pytest.approx(4.0)
    )
    assert (
        result["reward_points"]
        == pytest.approx(10.0)
    )
    assert (
        result["take_profit"]
        == pytest.approx(110.0)
    )

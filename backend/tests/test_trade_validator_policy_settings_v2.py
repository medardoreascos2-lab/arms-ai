from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings


POLICY_ENV = {
    "minimum_reward_risk_ratio":
        "ARMS_MINIMUM_REWARD_RISK_RATIO",
    "minimum_stop_points":
        "ARMS_MINIMUM_STOP_POINTS",
    "maximum_stop_points":
        "ARMS_MAXIMUM_STOP_POINTS",
    "maximum_spread_points":
        "ARMS_MAXIMUM_SPREAD_POINTS",
    "minimum_atr_points":
        "ARMS_MINIMUM_ATR_POINTS",
    "maximum_signal_age_seconds":
        "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS",
}


VALID_POLICY = {
    "minimum_reward_risk_ratio": "2.5",
    "minimum_stop_points": "4.0",
    "maximum_stop_points": "45.0",
    "maximum_spread_points": "0.75",
    "minimum_atr_points": "3.5",
    "maximum_signal_age_seconds": "20",
}


def _configure_policy_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS",
        "5.0",
    )

    for field_name, env_name in POLICY_ENV.items():
        monkeypatch.setenv(
            env_name,
            VALID_POLICY[field_name],
        )


def test_trade_validator_policy_requires_explicit_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS",
        "5.0",
    )

    for env_name in POLICY_ENV.values():
        monkeypatch.delenv(
            env_name,
            raising=False,
        )

    with pytest.raises(ValueError):
        APISettings()


@pytest.mark.parametrize(
    ("field_name", "raw_value"),
    [
        ("minimum_reward_risk_ratio", ""),
        ("minimum_reward_risk_ratio", "abc"),
        ("minimum_reward_risk_ratio", "nan"),
        ("minimum_reward_risk_ratio", "inf"),
        ("minimum_reward_risk_ratio", "0"),
        ("minimum_reward_risk_ratio", "-1"),
        ("minimum_stop_points", "0"),
        ("maximum_stop_points", "0"),
        ("maximum_spread_points", "0"),
        ("minimum_atr_points", "0"),
        ("maximum_signal_age_seconds", "0"),
        ("maximum_signal_age_seconds", "-1"),
        ("maximum_signal_age_seconds", "1.5"),
    ],
)
def test_trade_validator_policy_rejects_invalid_environment(
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    raw_value: str,
) -> None:
    _configure_policy_environment(
        monkeypatch
    )

    env_name = POLICY_ENV[field_name]

    monkeypatch.setenv(
        env_name,
        raw_value,
    )

    with pytest.raises(
        (TypeError, ValueError),
        match=env_name,
    ):
        APISettings()


def test_trade_validator_policy_reads_explicit_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_policy_environment(
        monkeypatch
    )

    settings = APISettings()

    assert (
        settings.minimum_reward_risk_ratio
        == pytest.approx(2.5)
    )
    assert (
        settings.minimum_stop_points
        == pytest.approx(4.0)
    )
    assert (
        settings.maximum_stop_points
        == pytest.approx(45.0)
    )
    assert (
        settings.maximum_spread_points
        == pytest.approx(0.75)
    )
    assert (
        settings.minimum_atr_points
        == pytest.approx(3.5)
    )
    assert (
        settings.maximum_signal_age_seconds
        == 20
    )

    assert math.isfinite(
        settings.minimum_reward_risk_ratio
    )
    assert math.isfinite(
        settings.minimum_stop_points
    )
    assert math.isfinite(
        settings.maximum_stop_points
    )
    assert math.isfinite(
        settings.maximum_spread_points
    )
    assert math.isfinite(
        settings.minimum_atr_points
    )


def test_trade_validator_policy_rejects_inverted_stop_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_policy_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "ARMS_MINIMUM_STOP_POINTS",
        "50.0",
    )
    monkeypatch.setenv(
        "ARMS_MAXIMUM_STOP_POINTS",
        "10.0",
    )

    with pytest.raises(
        ValueError,
        match=(
            "maximum_stop_points"
            "|ARMS_MAXIMUM_STOP_POINTS"
        ),
    ):
        APISettings()


def test_production_trade_validator_uses_settings_authority() -> None:
    path = Path(
        "backend/api/app.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    calls = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(node.func)
        except Exception:
            continue

        if name == "TradeValidatorV2":
            calls.append(node)

    assert len(calls) == 1

    call = calls[0]

    actual = {}

    for keyword in call.keywords:
        if keyword.arg is None:
            continue

        actual[keyword.arg] = ast.unparse(
            keyword.value
        )

    expected = {
        "minimum_reward_risk_ratio":
            "settings.minimum_reward_risk_ratio",
        "minimum_stop_points":
            "settings.minimum_stop_points",
        "maximum_stop_points":
            "settings.maximum_stop_points",
        "maximum_spread_points":
            "settings.maximum_spread_points",
        "minimum_atr_points":
            "settings.minimum_atr_points",
        "maximum_signal_age_seconds":
            "settings.maximum_signal_age_seconds",
    }

    assert actual == expected


def test_trade_validator_production_constructor_has_no_policy_literals() -> None:
    path = Path(
        "backend/api/app.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    calls = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(node.func)
        except Exception:
            continue

        if name == "TradeValidatorV2":
            calls.append(node)

    assert len(calls) == 1

    call = calls[0]

    for keyword in call.keywords:
        if keyword.arg not in POLICY_ENV:
            continue

        assert not isinstance(
            keyword.value,
            ast.Constant,
        ), (
            f"{keyword.arg} todavía usa "
            "un literal productivo."
        )

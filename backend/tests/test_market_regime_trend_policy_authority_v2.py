from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings


APP_PATH = Path("backend/api/app.py")
SETTINGS_PATH = Path("backend/config/api_settings.py")

FIELD_NAME = "market_regime_trend_threshold"
ENV_NAME = "ARMS_MARKET_REGIME_TREND_THRESHOLD"

DEFAULT_VALUE = 0.60


def _app_source() -> str:
    return APP_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )


def _settings_source() -> str:
    return SETTINGS_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )


def _market_regime_trend_sources() -> list[str]:
    tree = ast.parse(_app_source())

    sources: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            call_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
        else:
            continue

        if call_name != "MarketRegimeEngine":
            continue

        for keyword in node.keywords:
            if keyword.arg == "trend_threshold":
                sources.append(
                    ast.unparse(keyword.value)
                )

    return sources


def _settings_with_env(
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
) -> APISettings:
    required_env = {
        "ARMS_MAXIMUM_OPEN_POSITIONS": "4",
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": "30",
        "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS": "300",
        "ARMS_MAXIMUM_SPREAD_POINTS": "10",
        "ARMS_MAXIMUM_STOP_POINTS": "200",
        "ARMS_MINIMUM_ATR_POINTS": "1",
        "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE": "0.8",
        "ARMS_MINIMUM_A_PLUS_PROBABILITY": "0.8",
        "ARMS_MINIMUM_EXECUTION_CONFIDENCE": "0.7",
        "ARMS_MINIMUM_PROBABILITY_APPROVAL": "0.8",
        "ARMS_MINIMUM_REWARD_RISK_RATIO": "1.5",
        "ARMS_MINIMUM_STOP_POINTS": "1",
        "ARMS_PAPER_EXECUTION_SLIPPAGE_POINTS": "0.25",
        "ARMS_TRAILING_STOP_ACTIVATION_POINTS": "30",
        "ARMS_TRAILING_STOP_DISTANCE_POINTS": "10",
    }

    for env_name, env_value in required_env.items():
        monkeypatch.setenv(
            env_name,
            env_value,
        )

    if value is None:
        monkeypatch.delenv(
            ENV_NAME,
            raising=False,
        )
    else:
        monkeypatch.setenv(
            ENV_NAME,
            value,
        )

    return APISettings()


def test_canonical_field_exists_in_settings_source():
    assert FIELD_NAME in _settings_source()


def test_canonical_environment_variable_exists_in_settings_source():
    assert ENV_NAME in _settings_source()


def test_default_market_regime_trend_threshold(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _settings_with_env(
        monkeypatch,
        None,
    )

    assert (
        settings.market_regime_trend_threshold
        == pytest.approx(DEFAULT_VALUE)
    )


@pytest.mark.parametrize(
    "value, expected",
    [
        ("0", 0.0),
        ("0.25", 0.25),
        ("0.60", 0.60),
        ("0.75", 0.75),
        ("1", 1.0),
        ("1.0", 1.0),
    ],
)
def test_valid_market_regime_trend_threshold_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    expected: float,
):
    settings = _settings_with_env(
        monkeypatch,
        value,
    )

    assert (
        settings.market_regime_trend_threshold
        == pytest.approx(expected)
    )


@pytest.mark.parametrize(
    "value",
    [
        "-0.01",
        "1.01",
        "nan",
        "NaN",
        "inf",
        "-inf",
        "",
        " ",
        "abc",
    ],
)
def test_invalid_market_regime_trend_threshold_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
):
    monkeypatch.setenv(
        ENV_NAME,
        value,
    )

    with pytest.raises(ValueError):
        APISettings()


def test_app_uses_canonical_market_regime_trend_threshold():
    sources = _market_regime_trend_sources()

    assert sources == [
        "settings.market_regime_trend_threshold"
    ]


def test_app_no_longer_owns_literal_trend_threshold():
    sources = _market_regime_trend_sources()

    assert "0.6" not in sources
    assert "0.60" not in sources


def test_market_regime_trend_threshold_is_independent_from_a_plus_policy():
    source = _settings_source()

    assert (
        "market_regime_trend_threshold"
        in source
    )

    assert (
        "minimum_a_plus_confluence_score"
        in source
    )

    assert (
        "minimum_a_plus_probability"
        in source
    )

    assert (
        "market_regime_trend_threshold"
        != "minimum_a_plus_confluence_score"
    )

    assert (
        "market_regime_trend_threshold"
        != "minimum_a_plus_probability"
    )


def test_market_regime_trend_threshold_is_independent_from_execution_confidence():
    source = _settings_source()

    assert (
        "market_regime_trend_threshold"
        in source
    )

    assert (
        "minimum_execution_confidence"
        in source
    )

    assert (
        "market_regime_trend_threshold"
        != "minimum_execution_confidence"
    )


def test_environment_name_is_exact():
    assert (
        ENV_NAME
        == "ARMS_MARKET_REGIME_TREND_THRESHOLD"
    )


def test_environment_is_not_mutated_by_contract():
    assert os.getenv(
        "ARMS_MARKET_REGIME_TREND_THRESHOLD"
    ) is None

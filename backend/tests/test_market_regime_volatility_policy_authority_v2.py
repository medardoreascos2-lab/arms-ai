from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings


APP_PATH = Path("backend/api/app.py")
SETTINGS_PATH = Path("backend/config/api_settings.py")

HIGH_FIELD = "market_regime_high_volatility_threshold"
LOW_FIELD = "market_regime_low_volatility_threshold"
COMPRESSION_FIELD = "market_regime_compression_threshold"

HIGH_ENV = "ARMS_MARKET_REGIME_HIGH_VOLATILITY_THRESHOLD"
LOW_ENV = "ARMS_MARKET_REGIME_LOW_VOLATILITY_THRESHOLD"
COMPRESSION_ENV = "ARMS_MARKET_REGIME_COMPRESSION_THRESHOLD"

DEFAULT_HIGH = 0.80
DEFAULT_LOW = 0.20
DEFAULT_COMPRESSION = 0.15


REQUIRED_UNRELATED_ENV = {
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


def _settings_source() -> str:
    return SETTINGS_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )


def _app_source() -> str:
    return APP_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )


def _market_regime_sources() -> dict[str, str]:
    tree = ast.parse(_app_source())

    found: list[dict[str, str]] = []

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

        values: dict[str, str] = {}

        for keyword in node.keywords:
            if keyword.arg is not None:
                values[keyword.arg] = ast.unparse(
                    keyword.value
                )

        found.append(values)

    assert len(found) == 1
    return found[0]


def _settings_with_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    high: str | None = None,
    low: str | None = None,
    compression: str | None = None,
) -> APISettings:
    for name, value in REQUIRED_UNRELATED_ENV.items():
        monkeypatch.setenv(name, value)

    targets = {
        HIGH_ENV: high,
        LOW_ENV: low,
        COMPRESSION_ENV: compression,
    }

    for name, value in targets.items():
        if value is None:
            monkeypatch.delenv(
                name,
                raising=False,
            )
        else:
            monkeypatch.setenv(
                name,
                value,
            )

    return APISettings()


@pytest.mark.parametrize(
    "field_name",
    [
        HIGH_FIELD,
        LOW_FIELD,
        COMPRESSION_FIELD,
    ],
)
def test_canonical_fields_exist(
    field_name: str,
):
    assert field_name in _settings_source()


@pytest.mark.parametrize(
    "env_name",
    [
        HIGH_ENV,
        LOW_ENV,
        COMPRESSION_ENV,
    ],
)
def test_canonical_environment_names_exist(
    env_name: str,
):
    assert env_name in _settings_source()


def test_default_market_regime_volatility_policy(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _settings_with_env(
        monkeypatch
    )

    assert (
        settings.market_regime_high_volatility_threshold
        == pytest.approx(DEFAULT_HIGH)
    )
    assert (
        settings.market_regime_low_volatility_threshold
        == pytest.approx(DEFAULT_LOW)
    )
    assert (
        settings.market_regime_compression_threshold
        == pytest.approx(DEFAULT_COMPRESSION)
    )


@pytest.mark.parametrize(
    "high,low,compression",
    [
        ("1", "0", "0"),
        ("0.90", "0.10", "0.20"),
        ("0.75", "0.25", "0.50"),
        ("0.60", "0.40", "1.0"),
    ],
)
def test_valid_market_regime_policy_values(
    monkeypatch: pytest.MonkeyPatch,
    high: str,
    low: str,
    compression: str,
):
    settings = _settings_with_env(
        monkeypatch,
        high=high,
        low=low,
        compression=compression,
    )

    assert (
        settings.market_regime_high_volatility_threshold
        == pytest.approx(float(high))
    )
    assert (
        settings.market_regime_low_volatility_threshold
        == pytest.approx(float(low))
    )
    assert (
        settings.market_regime_compression_threshold
        == pytest.approx(float(compression))
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("high", "-0.01"),
        ("high", "1.01"),
        ("high", "nan"),
        ("high", "inf"),
        ("high", ""),
        ("low", "-0.01"),
        ("low", "1.01"),
        ("low", "nan"),
        ("low", "inf"),
        ("low", ""),
        ("compression", "-0.01"),
        ("compression", "1.01"),
        ("compression", "nan"),
        ("compression", "inf"),
        ("compression", ""),
    ],
)
def test_invalid_unit_interval_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
):
    kwargs = {
        "high": "0.80",
        "low": "0.20",
        "compression": "0.15",
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        _settings_with_env(
            monkeypatch,
            **kwargs,
        )


@pytest.mark.parametrize(
    "high,low",
    [
        ("0.20", "0.20"),
        ("0.20", "0.80"),
        ("0", "0"),
        ("1", "1"),
    ],
)
def test_invalid_volatility_order_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    high: str,
    low: str,
):
    with pytest.raises(ValueError):
        _settings_with_env(
            monkeypatch,
            high=high,
            low=low,
            compression="0.15",
        )


def test_app_uses_canonical_market_regime_policy():
    values = _market_regime_sources()

    assert values[
        "high_volatility_threshold"
    ] == (
        "settings."
        "market_regime_high_volatility_threshold"
    )

    assert values[
        "low_volatility_threshold"
    ] == (
        "settings."
        "market_regime_low_volatility_threshold"
    )

    assert values[
        "compression_threshold"
    ] == (
        "settings."
        "market_regime_compression_threshold"
    )


def test_app_no_longer_owns_market_regime_literals():
    values = _market_regime_sources()

    assert values[
        "high_volatility_threshold"
    ] not in {"0.8", "0.80"}

    assert values[
        "low_volatility_threshold"
    ] not in {"0.2", "0.20"}

    assert values[
        "compression_threshold"
    ] not in {"0.15"}


def test_policy_fields_are_independent():
    assert HIGH_FIELD != LOW_FIELD
    assert HIGH_FIELD != COMPRESSION_FIELD
    assert LOW_FIELD != COMPRESSION_FIELD

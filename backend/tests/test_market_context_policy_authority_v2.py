from __future__ import annotations

import ast
import math
import os
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings


MINIMUM_CANDLES_FIELD = (
    "market_context_minimum_candles"
)
LOOKBACK_FIELD = (
    "market_context_internal_range_lookback"
)
NEAR_EXTREME_FIELD = (
    "market_context_near_extreme_threshold"
)
EQUILIBRIUM_FIELD = (
    "market_context_equilibrium_tolerance"
)
DECISION_FIELD = (
    "market_context_decision_threshold"
)

MINIMUM_CANDLES_ENV = (
    "ARMS_MARKET_CONTEXT_MINIMUM_CANDLES"
)
LOOKBACK_ENV = (
    "ARMS_MARKET_CONTEXT_INTERNAL_RANGE_LOOKBACK"
)
NEAR_EXTREME_ENV = (
    "ARMS_MARKET_CONTEXT_NEAR_EXTREME_THRESHOLD"
)
EQUILIBRIUM_ENV = (
    "ARMS_MARKET_CONTEXT_EQUILIBRIUM_TOLERANCE"
)
DECISION_ENV = (
    "ARMS_MARKET_CONTEXT_DECISION_THRESHOLD"
)

TARGET_ENVS = (
    MINIMUM_CANDLES_ENV,
    LOOKBACK_ENV,
    NEAR_EXTREME_ENV,
    EQUILIBRIUM_ENV,
    DECISION_ENV,
)

UNRELATED_REQUIRED_ENV = {
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


def _prepare_env(
    monkeypatch: pytest.MonkeyPatch,
    **target_values: str,
) -> None:
    for key in tuple(os.environ):
        if key.startswith("ARMS_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )

    for key, value in UNRELATED_REQUIRED_ENV.items():
        monkeypatch.setenv(
            key,
            value,
        )

    for key in TARGET_ENVS:
        monkeypatch.delenv(
            key,
            raising=False,
        )

    for key, value in target_values.items():
        monkeypatch.setenv(
            key,
            value,
        )


def _settings(
    monkeypatch: pytest.MonkeyPatch,
    **target_values: str,
) -> APISettings:
    _prepare_env(
        monkeypatch,
        **target_values,
    )
    return APISettings()


def _market_context_call() -> ast.Call:
    path = Path("backend/api/app.py")

    source = path.read_text(
        encoding="utf-8",
        errors="strict",
    )

    tree = ast.parse(source)

    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue

        if name == "MarketContextEngineV2":
            calls.append(node)

    assert len(calls) == 1

    return calls[0]


def _keyword_map(
    call: ast.Call,
) -> dict[str, str]:
    return {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in call.keywords
        if keyword.arg is not None
    }


@pytest.mark.parametrize(
    ("field_name", "expected"),
    (
        (MINIMUM_CANDLES_FIELD, 5),
        (LOOKBACK_FIELD, 10),
        (NEAR_EXTREME_FIELD, 0.10),
        (EQUILIBRIUM_FIELD, 0.05),
        (DECISION_FIELD, 0.25),
    ),
)
def test_market_context_policy_defaults_are_canonical(
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    expected: float,
) -> None:
    settings = _settings(monkeypatch)

    assert hasattr(
        settings,
        field_name,
    )

    assert getattr(
        settings,
        field_name,
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("environment_name", "field_name", "value"),
    (
        (
            MINIMUM_CANDLES_ENV,
            MINIMUM_CANDLES_FIELD,
            "6",
        ),
        (
            LOOKBACK_ENV,
            LOOKBACK_FIELD,
            "12",
        ),
        (
            NEAR_EXTREME_ENV,
            NEAR_EXTREME_FIELD,
            "0.20",
        ),
        (
            EQUILIBRIUM_ENV,
            EQUILIBRIUM_FIELD,
            "0.10",
        ),
        (
            DECISION_ENV,
            DECISION_FIELD,
            "0.30",
        ),
    ),
)
def test_market_context_policy_env_overrides_are_canonical(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    field_name: str,
    value: str,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            environment_name: value,
        },
    )

    assert float(
        getattr(
            settings,
            field_name,
        )
    ) == pytest.approx(
        float(value)
    )


@pytest.mark.parametrize(
    ("environment_name", "invalid_value"),
    (
        (MINIMUM_CANDLES_ENV, "0"),
        (MINIMUM_CANDLES_ENV, "1"),
        (MINIMUM_CANDLES_ENV, "2"),
        (MINIMUM_CANDLES_ENV, "-1"),
        (MINIMUM_CANDLES_ENV, "1.5"),
        (MINIMUM_CANDLES_ENV, "true"),
        (MINIMUM_CANDLES_ENV, ""),
        (MINIMUM_CANDLES_ENV, " "),
        (MINIMUM_CANDLES_ENV, "text"),
        (LOOKBACK_ENV, "0"),
        (LOOKBACK_ENV, "1"),
        (LOOKBACK_ENV, "2"),
        (LOOKBACK_ENV, "-1"),
        (LOOKBACK_ENV, "1.5"),
        (LOOKBACK_ENV, "true"),
        (LOOKBACK_ENV, ""),
        (LOOKBACK_ENV, " "),
        (LOOKBACK_ENV, "text"),
    ),
)
def test_market_context_integer_policies_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        **{
            environment_name: invalid_value,
        },
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    ("environment_name", "field_name"),
    (
        (
            MINIMUM_CANDLES_ENV,
            MINIMUM_CANDLES_FIELD,
        ),
        (
            LOOKBACK_ENV,
            LOOKBACK_FIELD,
        ),
    ),
)
def test_market_context_integer_policies_accept_lower_boundary(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    field_name: str,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            environment_name: "3",
        },
    )

    assert getattr(
        settings,
        field_name,
    ) == 3

    assert isinstance(
        getattr(
            settings,
            field_name,
        ),
        int,
    )


@pytest.mark.parametrize(
    ("environment_name", "invalid_value"),
    (
        (NEAR_EXTREME_ENV, "0"),
        (NEAR_EXTREME_ENV, "-0.01"),
        (NEAR_EXTREME_ENV, "1.01"),
        (NEAR_EXTREME_ENV, "nan"),
        (NEAR_EXTREME_ENV, "inf"),
        (NEAR_EXTREME_ENV, "-inf"),
        (NEAR_EXTREME_ENV, ""),
        (NEAR_EXTREME_ENV, " "),
        (NEAR_EXTREME_ENV, "text"),
        (DECISION_ENV, "0"),
        (DECISION_ENV, "-0.01"),
        (DECISION_ENV, "1.01"),
        (DECISION_ENV, "nan"),
        (DECISION_ENV, "inf"),
        (DECISION_ENV, "-inf"),
        (DECISION_ENV, ""),
        (DECISION_ENV, " "),
        (DECISION_ENV, "text"),
    ),
)
def test_market_context_nonzero_ratios_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        **{
            environment_name: invalid_value,
        },
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    "invalid_value",
    (
        "-0.01",
        "1.01",
        "nan",
        "inf",
        "-inf",
        "",
        " ",
        "text",
    ),
)
def test_market_context_equilibrium_tolerance_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        **{
            EQUILIBRIUM_ENV: invalid_value,
        },
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


def test_market_context_equilibrium_tolerance_accepts_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            EQUILIBRIUM_ENV: "0",
        },
    )

    assert math.isclose(
        float(
            getattr(
                settings,
                EQUILIBRIUM_FIELD,
            )
        ),
        0.0,
    )


@pytest.mark.parametrize(
    ("environment_name", "field_name"),
    (
        (
            NEAR_EXTREME_ENV,
            NEAR_EXTREME_FIELD,
        ),
        (
            EQUILIBRIUM_ENV,
            EQUILIBRIUM_FIELD,
        ),
        (
            DECISION_ENV,
            DECISION_FIELD,
        ),
    ),
)
def test_market_context_ratio_policies_accept_upper_boundary(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    field_name: str,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            environment_name: "1",
        },
    )

    assert math.isclose(
        float(
            getattr(
                settings,
                field_name,
            )
        ),
        1.0,
    )


@pytest.mark.parametrize(
    ("keyword_name", "settings_expression"),
    (
        (
            "minimum_candles",
            "settings.market_context_minimum_candles",
        ),
        (
            "internal_range_lookback",
            "settings.market_context_internal_range_lookback",
        ),
        (
            "near_extreme_threshold",
            "settings.market_context_near_extreme_threshold",
        ),
        (
            "equilibrium_tolerance",
            "settings.market_context_equilibrium_tolerance",
        ),
        (
            "decision_threshold",
            "settings.market_context_decision_threshold",
        ),
    ),
)
def test_market_context_engine_app_wiring_uses_canonical_settings(
    keyword_name: str,
    settings_expression: str,
) -> None:
    values = _keyword_map(
        _market_context_call()
    )

    assert values[
        keyword_name
    ] == settings_expression


def test_market_context_policy_fields_are_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            MINIMUM_CANDLES_ENV: "6",
            LOOKBACK_ENV: "12",
            NEAR_EXTREME_ENV: "0.20",
            EQUILIBRIUM_ENV: "0.10",
            DECISION_ENV: "0.30",
        },
    )

    assert getattr(
        settings,
        MINIMUM_CANDLES_FIELD,
    ) == 6

    assert getattr(
        settings,
        LOOKBACK_FIELD,
    ) == 12

    assert getattr(
        settings,
        NEAR_EXTREME_FIELD,
    ) == pytest.approx(0.20)

    assert getattr(
        settings,
        EQUILIBRIUM_FIELD,
    ) == pytest.approx(0.10)

    assert getattr(
        settings,
        DECISION_FIELD,
    ) == pytest.approx(0.30)


def test_existing_market_context_engine_defaults_remain_parameterized(
) -> None:
    path = Path(
        "backend/context/"
        "market_context_engine_v2.py"
    )

    source = path.read_text(
        encoding="utf-8",
        errors="strict",
    )

    assert "minimum_candles: int = 5" in source
    assert "internal_range_lookback: int = 10" in source
    assert "near_extreme_threshold: float = 0.10" in source
    assert "equilibrium_tolerance: float = 0.05" in source
    assert "decision_threshold: float = 0.25" in source

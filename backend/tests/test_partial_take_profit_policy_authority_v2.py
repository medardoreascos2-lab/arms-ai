from __future__ import annotations

import ast
import math
import os
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings
from backend.execution.partial_take_profit_engine_v2 import (
    PartialTakeProfitEngineV2,
)


TRIGGER_FIELD = (
    "partial_take_profit_trigger_profit_points"
)
FRACTION_FIELD = (
    "partial_take_profit_close_fraction"
)

TRIGGER_ENV = (
    "ARMS_PARTIAL_TAKE_PROFIT_TRIGGER_PROFIT_POINTS"
)
FRACTION_ENV = (
    "ARMS_PARTIAL_TAKE_PROFIT_CLOSE_FRACTION"
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
    "ARMS_SIGNAL_EXECUTION_COOLDOWN_MINUTES": "15",
    "ARMS_BREAK_EVEN_TRIGGER_PROFIT_POINTS": "15",
    "ARMS_BREAK_EVEN_OFFSET_POINTS": "1",
}


def _prepare_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    trigger: str | None = None,
    fraction: str | None = None,
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

    monkeypatch.delenv(
        TRIGGER_ENV,
        raising=False,
    )

    monkeypatch.delenv(
        FRACTION_ENV,
        raising=False,
    )

    if trigger is not None:
        monkeypatch.setenv(
            TRIGGER_ENV,
            trigger,
        )

    if fraction is not None:
        monkeypatch.setenv(
            FRACTION_ENV,
            fraction,
        )


def _settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    trigger: str | None = None,
    fraction: str | None = None,
) -> APISettings:
    _prepare_env(
        monkeypatch,
        trigger=trigger,
        fraction=fraction,
    )

    return APISettings()


def _partial_take_profit_engine_call() -> ast.Call:
    path = Path(
        "backend/api/app.py"
    )

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

        if name == "PartialTakeProfitEngineV2":
            calls.append(node)

    assert len(calls) == 1

    return calls[0]


def test_partial_take_profit_policy_defaults_are_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
    )

    assert getattr(
        settings,
        TRIGGER_FIELD,
    ) == 20.0

    assert getattr(
        settings,
        FRACTION_FIELD,
    ) == 0.5


def test_partial_take_profit_policy_env_overrides_are_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        trigger="25.5",
        fraction="0.25",
    )

    assert getattr(
        settings,
        TRIGGER_FIELD,
    ) == 25.5

    assert getattr(
        settings,
        FRACTION_FIELD,
    ) == 0.25


@pytest.mark.parametrize(
    "invalid_value",
    (
        "0",
        "-1",
        "-0.1",
        "nan",
        "NaN",
        "inf",
        "+inf",
        "-inf",
        "",
        " ",
        "text",
    ),
)
def test_partial_take_profit_trigger_rejects_invalid_external_policy(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        trigger=invalid_value,
        fraction="0.5",
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    "valid_value",
    (
        "0.1",
        "1",
        "20",
        "25.5",
        "100",
    ),
)
def test_partial_take_profit_trigger_accepts_positive_finite_policy(
    monkeypatch: pytest.MonkeyPatch,
    valid_value: str,
) -> None:
    settings = _settings(
        monkeypatch,
        trigger=valid_value,
        fraction="0.5",
    )

    value = getattr(
        settings,
        TRIGGER_FIELD,
    )

    assert value == float(valid_value)
    assert math.isfinite(value)
    assert value > 0


@pytest.mark.parametrize(
    "invalid_value",
    (
        "-1",
        "-0.1",
        "0",
        "1",
        "1.1",
        "nan",
        "NaN",
        "inf",
        "+inf",
        "-inf",
        "",
        " ",
        "text",
    ),
)
def test_partial_take_profit_fraction_rejects_invalid_external_policy(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        trigger="20",
        fraction=invalid_value,
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    "valid_value",
    (
        "0.01",
        "0.1",
        "0.25",
        "0.5",
        "0.999",
    ),
)
def test_partial_take_profit_fraction_accepts_strict_unit_interval_policy(
    monkeypatch: pytest.MonkeyPatch,
    valid_value: str,
) -> None:
    settings = _settings(
        monkeypatch,
        trigger="20",
        fraction=valid_value,
    )

    value = getattr(
        settings,
        FRACTION_FIELD,
    )

    assert value == float(valid_value)
    assert math.isfinite(value)
    assert 0 < value < 1


def test_partial_take_profit_app_wiring_uses_canonical_settings(
) -> None:
    call = _partial_take_profit_engine_call()

    values = {
        keyword.arg: ast.unparse(
            keyword.value
        )
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert values[
        "trigger_profit_points"
    ] == (
        "settings."
        "partial_take_profit_trigger_profit_points"
    )

    assert values[
        "close_fraction"
    ] == (
        "settings."
        "partial_take_profit_close_fraction"
    )


def test_partial_take_profit_engine_remains_parameterized(
) -> None:
    path = Path(
        "backend/execution/"
        "partial_take_profit_engine_v2.py"
    )

    source = path.read_text(
        encoding="utf-8",
        errors="strict",
    )

    assert (
        "trigger_profit_points: float"
        in source
    )

    assert (
        "close_fraction: float"
        in source
    )

    assert (
        "trigger_profit_points: float ="
        not in source
    )

    assert (
        "close_fraction: float ="
        not in source
    )


def test_partial_take_profit_engine_runtime_semantics_remain_unchanged(
) -> None:
    engine = PartialTakeProfitEngineV2(
        trigger_profit_points=20.0,
        close_fraction=0.5,
    )

    base = {
        "status": "OPEN",
        "direction": "LONG",
        "entry_price": 100.0,
        "quantity": 4.0,
        "partial_taken": False,
    }

    waiting = engine.apply(
        position=base,
        current_price=119.0,
    )

    assert waiting["executed"] is False
    assert waiting["status"] == "WAITING"

    result = engine.apply(
        position=base,
        current_price=120.0,
    )

    assert result["executed"] is True
    assert result["status"] == "PARTIAL_TAKEN"
    assert result["closed_quantity"] == 2.0
    assert result["remaining_quantity"] == 2.0
    assert result["close_fraction"] == 0.5
    assert result["trigger_profit_points"] == 20.0

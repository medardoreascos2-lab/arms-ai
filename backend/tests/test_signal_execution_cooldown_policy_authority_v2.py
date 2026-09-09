from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings
from backend.execution.signal_execution_manager import (
    SignalExecutionManager,
)


FIELD = "signal_execution_cooldown_minutes"

ENV = "ARMS_SIGNAL_EXECUTION_COOLDOWN_MINUTES"

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
    value: str | None = None,
) -> None:
    for key in tuple(os.environ):
        if key.startswith("ARMS_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )

    for key, env_value in UNRELATED_REQUIRED_ENV.items():
        monkeypatch.setenv(
            key,
            env_value,
        )

    monkeypatch.delenv(
        ENV,
        raising=False,
    )

    if value is not None:
        monkeypatch.setenv(
            ENV,
            value,
        )


def _settings(
    monkeypatch: pytest.MonkeyPatch,
    value: str | None = None,
) -> APISettings:
    _prepare_env(
        monkeypatch,
        value,
    )
    return APISettings()


def _signal_execution_manager_call() -> ast.Call:
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

        if name == "SignalExecutionManager":
            calls.append(node)

    assert len(calls) == 1

    return calls[0]


def test_signal_execution_cooldown_default_is_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)

    assert hasattr(
        settings,
        FIELD,
    )

    assert getattr(
        settings,
        FIELD,
    ) == 15


def test_signal_execution_cooldown_env_override_is_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        "7",
    )

    assert getattr(
        settings,
        FIELD,
    ) == 7

    assert isinstance(
        getattr(
            settings,
            FIELD,
        ),
        int,
    )


@pytest.mark.parametrize(
    "invalid_value",
    (
        "-1",
        "1.5",
        "true",
        "false",
        "",
        " ",
        "text",
    ),
)
def test_signal_execution_cooldown_rejects_invalid_external_policy(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        invalid_value,
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    "valid_value",
    (
        "0",
        "1",
        "15",
        "60",
    ),
)
def test_signal_execution_cooldown_accepts_nonnegative_integer_policy(
    monkeypatch: pytest.MonkeyPatch,
    valid_value: str,
) -> None:
    settings = _settings(
        monkeypatch,
        valid_value,
    )

    value = getattr(
        settings,
        FIELD,
    )

    assert value == int(valid_value)
    assert isinstance(
        value,
        int,
    )


def test_signal_execution_manager_app_wiring_uses_canonical_setting(
) -> None:
    call = _signal_execution_manager_call()

    values = {
        keyword.arg: ast.unparse(
            keyword.value
        )
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert values[
        "cooldown_minutes"
    ] == (
        "settings."
        "signal_execution_cooldown_minutes"
    )


def test_engine_default_remains_parameterized(
) -> None:
    path = Path(
        "backend/execution/"
        "signal_execution_manager.py"
    )

    source = path.read_text(
        encoding="utf-8",
        errors="strict",
    )

    assert (
        "cooldown_minutes: int = 15"
        in source
    )


def test_engine_runtime_semantics_remain_unchanged(
) -> None:
    manager = SignalExecutionManager(
        cooldown_minutes=0,
    )

    assert manager.cooldown.total_seconds() == 0

    manager = SignalExecutionManager(
        cooldown_minutes=15,
    )

    assert (
        manager.cooldown.total_seconds()
        == 15 * 60
    )

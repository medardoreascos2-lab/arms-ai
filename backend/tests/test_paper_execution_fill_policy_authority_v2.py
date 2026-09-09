import ast
import importlib
import os
from pathlib import Path

import pytest


API_SETTINGS_PATH = Path(
    "backend/config/api_settings.py"
)
APP_PATH = Path(
    "backend/api/app.py"
)


def _api_settings_source() -> str:
    return API_SETTINGS_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )


def _app_tree() -> ast.AST:
    source = APP_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )
    return ast.parse(source)


def _paper_execution_calls(
    tree: ast.AST,
) -> list[ast.Call]:
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

        if name == "PaperExecutionEngineV2":
            calls.append(node)

    return calls


def test_api_settings_declares_paper_fill_policy():
    source = _api_settings_source()

    assert (
        "paper_execution_fill_market_orders_immediately"
        in source
    )


def test_api_settings_declares_paper_fill_environment_authority():
    source = _api_settings_source()

    assert (
        "ARMS_PAPER_EXECUTION_FILL_MARKET_ORDERS_IMMEDIATELY"
        in source
    )


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
    ],
)
def test_api_settings_parses_paper_fill_boolean(
    monkeypatch,
    raw_value,
    expected,
):
    env_name = (
        "ARMS_PAPER_EXECUTION_FILL_MARKET_ORDERS_IMMEDIATELY"
    )

    monkeypatch.setenv(
        env_name,
        raw_value,
    )

    import backend.config.api_settings as module

    module = importlib.reload(module)

    settings = module.APISettings()

    assert (
        settings.paper_execution_fill_market_orders_immediately
        is expected
    )


def test_api_settings_defaults_paper_fill_to_true(
    monkeypatch,
):
    env_name = (
        "ARMS_PAPER_EXECUTION_FILL_MARKET_ORDERS_IMMEDIATELY"
    )

    monkeypatch.delenv(
        env_name,
        raising=False,
    )

    import backend.config.api_settings as module

    module = importlib.reload(module)

    settings = module.APISettings()

    assert (
        settings.paper_execution_fill_market_orders_immediately
        is True
    )


@pytest.mark.parametrize(
    "raw_value",
    [
        "",
        "maybe",
        "enabled",
        "disabled",
        "2",
        "-1",
    ],
)
def test_api_settings_rejects_invalid_paper_fill_boolean(
    monkeypatch,
    raw_value,
):
    env_name = (
        "ARMS_PAPER_EXECUTION_FILL_MARKET_ORDERS_IMMEDIATELY"
    )

    monkeypatch.setenv(
        env_name,
        raw_value,
    )

    import backend.config.api_settings as module

    module = importlib.reload(module)

    with pytest.raises(
        ValueError,
        match=(
            "ARMS_PAPER_EXECUTION_FILL_MARKET_ORDERS_IMMEDIATELY"
        ),
    ):
        module.APISettings()


def test_app_uses_settings_authority_for_paper_fill():
    tree = _app_tree()

    calls = _paper_execution_calls(tree)

    assert len(calls) == 1

    values = {
        keyword.arg: keyword.value
        for keyword in calls[0].keywords
        if keyword.arg is not None
    }

    assert (
        "fill_market_orders_immediately"
        in values
    )

    value = values[
        "fill_market_orders_immediately"
    ]

    assert isinstance(value, ast.Attribute)
    assert value.attr == (
        "paper_execution_fill_market_orders_immediately"
    )

    assert isinstance(value.value, ast.Name)
    assert value.value.id == "settings"


def test_app_does_not_hardcode_paper_fill_true():
    tree = _app_tree()

    calls = _paper_execution_calls(tree)

    assert len(calls) == 1

    values = {
        keyword.arg: keyword.value
        for keyword in calls[0].keywords
        if keyword.arg is not None
    }

    value = values[
        "fill_market_orders_immediately"
    ]

    assert not (
        isinstance(value, ast.Constant)
        and value.value is True
    )

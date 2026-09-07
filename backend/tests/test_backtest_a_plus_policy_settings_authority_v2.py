from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from backend.api.app import create_app
from backend.backtesting.parameter_backtest_engine_factory_v2 import (
    ParameterBacktestEngineFactoryV2,
)
from backend.backtesting.strategy_backtest_factory_v2 import (
    build_signal_generator,
    build_strategy_backtest_pipeline,
)
from backend.config.api_settings import APISettings


def _configure_required_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    probability: str = "0.91",
    confluence: str = "0.92",
) -> None:
    monkeypatch.setenv(
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS",
        "5.0",
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_REWARD_RISK_RATIO",
        "2.0",
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
    monkeypatch.setenv(
        "ARMS_MINIMUM_A_PLUS_PROBABILITY",
        probability,
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE",
        confluence,
    )


def _factory_source() -> str:
    return Path(
        "backend/backtesting/"
        "strategy_backtest_factory_v2.py"
    ).read_text(
        encoding="utf-8"
    )


def _factory_tree() -> ast.Module:
    return ast.parse(
        _factory_source()
    )


def _app_tree() -> ast.Module:
    return ast.parse(
        Path(
            "backend/api/app.py"
        ).read_text(
            encoding="utf-8"
        )
    )


def _parameter_factory_tree() -> ast.Module:
    return ast.parse(
        Path(
            "backend/backtesting/"
            "parameter_backtest_engine_factory_v2.py"
        ).read_text(
            encoding="utf-8"
        )
    )


def _function(
    tree: ast.Module,
    name: str,
) -> ast.FunctionDef:
    found = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        )
    ]

    assert len(found) == 1

    return found[0]


def test_build_signal_generator_requires_explicit_settings() -> None:
    signature = inspect.signature(
        build_signal_generator
    )

    assert "settings" in signature.parameters

    parameter = signature.parameters[
        "settings"
    ]

    assert (
        parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        parameter.default
        is inspect.Parameter.empty
    )


def test_build_signal_generator_uses_settings_a_plus_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_environment(
        monkeypatch,
        probability="0.91",
        confluence="0.92",
    )

    settings = APISettings()

    signal = build_signal_generator(
        settings=settings
    )

    assert (
        signal.minimum_probability
        == settings.minimum_a_plus_probability
        == pytest.approx(0.91)
    )

    assert (
        signal.minimum_confluence_score
        == settings.minimum_a_plus_confluence_score
        == pytest.approx(0.92)
    )


def test_build_strategy_backtest_pipeline_requires_explicit_settings() -> None:
    signature = inspect.signature(
        build_strategy_backtest_pipeline
    )

    assert "settings" in signature.parameters

    parameter = signature.parameters[
        "settings"
    ]

    assert (
        parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        parameter.default
        is inspect.Parameter.empty
    )


def test_pipeline_propagates_settings_to_signal_generator_static() -> None:
    tree = _factory_tree()

    function = _function(
        tree,
        "build_strategy_backtest_pipeline",
    )

    calls = []

    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(
                node.func
            ).split(".")[-1]
        except Exception:
            continue

        if name == "build_signal_generator":
            calls.append(node)

    assert len(calls) == 1

    keyword_values = {
        keyword.arg:
            ast.unparse(keyword.value)
        for keyword in calls[0].keywords
        if keyword.arg is not None
    }

    assert (
        keyword_values.get("settings")
        == "settings"
    )


def test_parameter_backtest_factory_requires_explicit_settings() -> None:
    signature = inspect.signature(
        ParameterBacktestEngineFactoryV2
    )

    assert "settings" in signature.parameters

    parameter = signature.parameters[
        "settings"
    ]

    assert (
        parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        parameter.default
        is inspect.Parameter.empty
    )


def test_parameter_backtest_factory_propagates_settings_static() -> None:
    tree = _parameter_factory_tree()

    cls = next(
        (
            node
            for node in tree.body
            if (
                isinstance(node, ast.ClassDef)
                and node.name
                == "ParameterBacktestEngineFactoryV2"
            )
        ),
        None,
    )

    assert cls is not None

    call_method = next(
        (
            node
            for node in cls.body
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "__call__"
            )
        ),
        None,
    )

    assert call_method is not None

    calls = []

    for node in ast.walk(call_method):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(
                node.func
            ).split(".")[-1]
        except Exception:
            continue

        if name == "build_strategy_backtest_pipeline":
            calls.append(node)

    assert len(calls) == 1

    keyword_values = {
        keyword.arg:
            ast.unparse(keyword.value)
        for keyword in calls[0].keywords
        if keyword.arg is not None
    }

    assert (
        keyword_values.get("settings")
        == "self.settings"
    )


def test_app_direct_backtest_pipeline_propagates_settings_static() -> None:
    tree = _app_tree()

    create_app_node = _function(
        tree,
        "create_app",
    )

    calls = []

    for node in ast.walk(create_app_node):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(
                node.func
            ).split(".")[-1]
        except Exception:
            continue

        if name == "build_strategy_backtest_pipeline":
            calls.append(node)

    assert len(calls) == 1

    keyword_values = {
        keyword.arg:
            ast.unparse(keyword.value)
        for keyword in calls[0].keywords
        if keyword.arg is not None
    }

    assert (
        keyword_values.get("settings")
        == "settings"
    )


def test_app_parameter_factory_propagates_settings_static() -> None:
    tree = _app_tree()

    create_app_node = _function(
        tree,
        "create_app",
    )

    calls = []

    for node in ast.walk(create_app_node):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(
                node.func
            ).split(".")[-1]
        except Exception:
            continue

        if name == "ParameterBacktestEngineFactoryV2":
            calls.append(node)

    assert len(calls) == 1

    keyword_values = {
        keyword.arg:
            ast.unparse(keyword.value)
        for keyword in calls[0].keywords
        if keyword.arg is not None
    }

    assert (
        keyword_values.get("settings")
        == "settings"
    )


def test_backtest_factory_has_no_a_plus_threshold_literals() -> None:
    tree = _factory_tree()

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

        if name == "SignalGeneratorV2":
            calls.append(node)

    assert len(calls) == 1

    matching = [
        keyword
        for keyword in calls[0].keywords
        if keyword.arg in {
            "minimum_probability",
            "minimum_confluence_score",
        }
    ]

    assert len(matching) == 2

    for keyword in matching:
        assert not isinstance(
            keyword.value,
            ast.Constant,
        ), (
            f"{keyword.arg} todavía usa "
            "un literal productivo."
        )


def test_backtest_factory_uses_settings_authority_static() -> None:
    tree = _factory_tree()

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

        if name == "SignalGeneratorV2":
            calls.append(node)

    assert len(calls) == 1

    keyword_values = {
        keyword.arg:
            ast.unparse(keyword.value)
        for keyword in calls[0].keywords
        if keyword.arg is not None
    }

    assert {
        "minimum_probability":
            keyword_values.get(
                "minimum_probability"
            ),
        "minimum_confluence_score":
            keyword_values.get(
                "minimum_confluence_score"
            ),
    } == {
        "minimum_probability":
            "settings.minimum_a_plus_probability",
        "minimum_confluence_score":
            "settings.minimum_a_plus_confluence_score",
    }


def test_live_and_backtest_generators_share_runtime_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_environment(
        monkeypatch,
        probability="0.91",
        confluence="0.92",
    )

    settings = APISettings()

    app = create_app(
        settings=settings
    )

    live_signal = (
        app.state.signal_generator_v2
    )

    backtest_signal = (
        build_signal_generator(
            settings=settings
        )
    )

    assert (
        live_signal.minimum_probability
        == backtest_signal.minimum_probability
        == settings.minimum_a_plus_probability
        == pytest.approx(0.91)
    )

    assert (
        live_signal.minimum_confluence_score
        == backtest_signal.minimum_confluence_score
        == settings.minimum_a_plus_confluence_score
        == pytest.approx(0.92)
    )

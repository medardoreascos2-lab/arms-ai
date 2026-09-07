from pathlib import Path
import ast


API_SETTINGS = Path("backend/config/api_settings.py")
RUNTIME_CONTEXT = Path(
    "backend/services/runtime_context_v2.py"
)
STRATEGY_BACKTEST = Path(
    "backend/backtesting/strategy_backtest_factory_v2.py"
)
BACKTEST_ADAPTER = Path(
    "backend/backtesting/backtest_risk_adapter_factory_v2.py"
)


def _text(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def _risk_manager_max_open_values(
    path: Path,
) -> list[str]:
    tree = ast.parse(_text(path))
    values: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        is_risk_manager = (
            isinstance(func, ast.Name)
            and func.id == "RiskManagerV2"
        ) or (
            isinstance(func, ast.Attribute)
            and func.attr == "RiskManagerV2"
        )

        if not is_risk_manager:
            continue

        for keyword in node.keywords:
            if (
                keyword.arg
                == "maximum_open_positions"
            ):
                values.append(
                    ast.unparse(keyword.value)
                )

    return values


def _create_default_for_max_open_positions(
    path: Path,
) -> str | None:
    tree = ast.parse(_text(path))

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        if node.name != "create":
            continue

        positional = list(node.args.args)
        positional_defaults = list(
            node.args.defaults
        )

        offset = (
            len(positional)
            - len(positional_defaults)
        )

        for index, arg in enumerate(positional):
            if arg.arg != "maximum_open_positions":
                continue

            if index < offset:
                return None

            return ast.unparse(
                positional_defaults[
                    index - offset
                ]
            )

        for arg, default in zip(
            node.args.kwonlyargs,
            node.args.kw_defaults,
        ):
            if arg.arg != "maximum_open_positions":
                continue

            if default is None:
                return None

            return ast.unparse(default)

    raise AssertionError(
        "BacktestRiskAdapterFactoryV2.create "
        "does not expose maximum_open_positions."
    )


def test_api_settings_declares_single_env_authority():
    source = _text(API_SETTINGS)

    assert (
        "maximum_open_positions: int"
        in source
    )
    assert (
        '"ARMS_MAXIMUM_OPEN_POSITIONS"'
        in source
    )


def test_runtime_context_does_not_hardcode_maximum_open_positions():
    values = _risk_manager_max_open_values(
        RUNTIME_CONTEXT
    )

    assert values, (
        "Runtime context must construct "
        "RiskManagerV2."
    )

    assert "1" not in values, (
        "runtime_context_v2 still owns a "
        "hardcoded maximum_open_positions=1 "
        f"policy: {values}"
    )


def test_runtime_context_consumes_api_settings_authority():
    source = _text(RUNTIME_CONTEXT)

    assert (
        "maximum_open_positions"
        in source
    )

    assert (
        "api_settings.maximum_open_positions"
        in source
    ), (
        "runtime_context_v2 must consume the "
        "APISettings maximum_open_positions "
        "authority."
    )


def test_strategy_backtest_does_not_hardcode_maximum_open_positions():
    values = _risk_manager_max_open_values(
        STRATEGY_BACKTEST
    )

    assert values, (
        "Strategy backtest factory must "
        "construct RiskManagerV2."
    )

    assert "1" not in values, (
        "strategy_backtest_factory_v2 still "
        "owns a hardcoded "
        "maximum_open_positions=1 policy: "
        f"{values}"
    )


def test_strategy_backtest_consumes_api_settings_authority():
    source = _text(STRATEGY_BACKTEST)

    assert (
        "resolved_settings.maximum_open_positions"
        in source
    ), (
        "strategy_backtest_factory_v2 must "
        "consume the resolved APISettings "
        "maximum_open_positions authority."
    )

    assert (
        "settings=settings"
        in source
    ), (
        "strategy backtest pipeline must "
        "propagate settings into build_lifecycle."
    )


def test_backtest_adapter_explicit_override_remains_parameterized():
    source = _text(BACKTEST_ADAPTER)
    values = _risk_manager_max_open_values(
        BACKTEST_ADAPTER
    )

    assert (
        "maximum_open_positions"
        in source
    )

    assert (
        "maximum_open_positions"
        in values
    ), (
        "Backtest adapter must continue "
        "passing its explicit parameter to "
        "RiskManagerV2."
    )


def test_backtest_adapter_default_is_classified_not_silently_removed():
    default = (
        _create_default_for_max_open_positions(
            BACKTEST_ADAPTER
        )
    )

    assert default == "1", (
        "This RED contract intentionally "
        "classifies the adapter default as "
        "legacy compatibility behavior. "
        "Do not silently change/remove it "
        "while fixing runtime/backtest "
        "composition authority."
    )

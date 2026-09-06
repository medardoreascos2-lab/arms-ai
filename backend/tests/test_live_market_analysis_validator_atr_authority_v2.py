import ast
from pathlib import Path


LIVE = Path(
    "backend/services/live_market_analysis_service.py"
)


def _analyze_function() -> ast.FunctionDef:
    tree = ast.parse(
        LIVE.read_text(
            encoding="utf-8",
        )
    )

    for node in ast.walk(tree):
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name == "analyze"
        ):
            return node

    raise AssertionError(
        "LiveMarketAnalysisService.analyze no encontrado."
    )


def _validator_call() -> ast.Call:
    analyze = _analyze_function()

    calls = []

    for node in ast.walk(analyze):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        func = node.func

        if (
            isinstance(
                func,
                ast.Attribute,
            )
            and func.attr == "validate"
            and isinstance(
                func.value,
                ast.Attribute,
            )
            and func.value.attr
            == "trade_validator_v2"
        ):
            calls.append(node)

    assert len(calls) == 1

    return calls[0]


def _keyword_value(
    call: ast.Call,
    keyword_name: str,
) -> ast.AST:
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return keyword.value

    raise AssertionError(
        f"Keyword {keyword_name!r} no encontrado."
    )


def test_validator_atr_is_not_static_literal():
    call = _validator_call()

    value = _keyword_value(
        call,
        "atr_points",
    )

    assert not isinstance(
        value,
        ast.Constant,
    ), (
        "TradeValidatorV2 no debe recibir "
        "un ATR literal estático."
    )


def test_validator_atr_comes_from_pipeline_context():
    call = _validator_call()

    value = _keyword_value(
        call,
        "atr_points",
    )

    source = ast.unparse(value)

    assert "context" in source, (
        "ATR del validator debe derivarse "
        "del contexto producido por IndicatorStage."
    )

    assert "atr" in source.lower(), (
        "La expresión debe consumir el ATR "
        "canónico del pipeline."
    )


def test_pipeline_runs_before_validator():
    analyze = _analyze_function()

    pipeline_run_lines = []
    validator_lines = []

    for node in ast.walk(analyze):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        func = node.func

        if (
            isinstance(
                func,
                ast.Attribute,
            )
            and func.attr == "run"
            and isinstance(
                func.value,
                ast.Name,
            )
            and func.value.id == "pipeline"
        ):
            pipeline_run_lines.append(
                node.lineno
            )

        if (
            isinstance(
                func,
                ast.Attribute,
            )
            and func.attr == "validate"
            and isinstance(
                func.value,
                ast.Attribute,
            )
            and func.value.attr
            == "trade_validator_v2"
        ):
            validator_lines.append(
                node.lineno
            )

    assert len(pipeline_run_lines) == 1
    assert len(validator_lines) == 1

    assert (
        pipeline_run_lines[0]
        < validator_lines[0]
    )


def test_indicator_stage_is_in_live_pipeline():
    analyze = _analyze_function()

    indicator_calls = []

    for node in ast.walk(analyze):
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "IndicatorStage"
        ):
            indicator_calls.append(node)

    assert len(indicator_calls) == 1

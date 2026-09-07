from pathlib import Path
import ast


LIVE_PATH = Path(
    "backend/services/live_market_analysis_service.py"
)


def _execution_v2_call() -> ast.Call:
    source = LIVE_PATH.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    calls = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(
                node.func
            )
        except Exception:
            continue

        if name == (
            "self.execution_decision_engine_v2.evaluate"
        ):
            calls.append(node)

    assert len(calls) == 1

    return calls[0]


def _keyword_values():
    call = _execution_v2_call()

    return {
        keyword.arg: keyword.value
        for keyword in call.keywords
        if keyword.arg is not None
    }


def _value(name: str) -> str:
    node = _keyword_values()[name]
    return ast.unparse(node)


def test_execution_v2_uses_runtime_account_risk_authority():
    assert _value(
        "risk_approved"
    ) == (
        "account_risk_approved "
        "if 'account_risk_approved' in locals() "
        "else True"
    )


def test_execution_v2_uses_runtime_position_sizing_authority():
    assert _value(
        "sizing_approved"
    ) == (
        "position_sizing_approved "
        "if 'position_sizing_approved' in locals() "
        "else True"
    )


def test_execution_v2_uses_runtime_open_position_authority():
    assert _value(
        "has_open_position"
    ) == "open_positions > 0"


def test_execution_v2_keeps_daily_limit_out_of_scope():
    assert _value(
        "daily_limit_reached"
    ) == "False"


def test_execution_v2_keeps_runtime_news_authority():
    assert _value(
        "news_blocked"
    ) == "news_blocked"


def test_execution_v2_has_no_static_allow_authority_bypass():
    values = _keyword_values()

    static_allow = {
        "risk_approved": True,
        "sizing_approved": True,
        "has_open_position": False,
    }

    violations = []

    for key, expected_literal in static_allow.items():
        node = values[key]

        if (
            isinstance(
                node,
                ast.Constant,
            )
            and node.value
            is expected_literal
        ):
            violations.append(
                key
            )

    assert violations == []

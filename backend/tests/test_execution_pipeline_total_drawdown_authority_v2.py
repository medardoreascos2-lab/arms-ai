"""A read-only pipeline must not construct or evaluate drawdown risk context."""
import ast
from pathlib import Path


ROUTER = Path("backend/api/routers/intelligence_decision_api_v3.py")


def test_pipeline_read_does_not_request_drawdown_or_evaluate_risk():
    tree = ast.parse(ROUTER.read_text(encoding="utf-8"))
    handler = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef)
                   and node.name == "execution_pipeline_v3")
    source = ast.unparse(handler)
    for name in ("total_drawdown", "risk_context", "account_state_manager_v2",
                 "evaluate_trade", "submit_signal"):
        assert name not in source

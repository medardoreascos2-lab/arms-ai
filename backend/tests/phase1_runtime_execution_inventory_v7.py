"""Discover construction and execution boundaries; classifications live in JSON.

Calls are lexical evidence, not dynamic dispatch claims. Module entry points and
nested route handlers are included. Independent tests verify the concrete graph.
"""
import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDERS = {
    "build_runtime_context", "create_runtime_lifespan", "create_asgi_app", "create_app",
    "RuntimeContextV2", "AccountRuntimeCoordinatorV2", "AccountRuntimeApplicationV2",
    "TradeLifecycleServiceV2", "ExecutionManagerV2", "PaperExecutionEngineV2",
    "PaperBrokerConnectorV2", "ExecutionStateStoreV2", "RuntimeLifecycleManagerV2",
    "StartupCoordinatorV2", "StateRecoveryServiceV2", "PortfolioManagerV2",
    "AccountStateManagerV2", "TradeJournalV2", "PositionManagerV2", "PositionManager",
    "ExecutionPipelineV2", "ExecutionPositionBridgeV1", "PositionLifecycleManagerV1",
    "TradeExecutorV2", "ExecutionServiceV2", "ExecutionEngineV2", "TradeExecutionEngine",
    "build_lifecycle", "build_strategy_backtest_pipeline",
}
EXECUTION = {
    "submit_order", "execute_order", "place_order", "send_order", "open_position",
    "close_position", "partial_close", "close_partial", "cancel_order", "replace_order",
    "modify_order", "create_protection", "create_oco", "create_group", "cancel_group",
    "cancel_remaining", "cancel_protection", "complete_protection", "process_signal",
    "execute_signal", "submit_signal", "prepare_order", "execute", "trade", "buy", "sell",
    "replace_active_position", "restore_active_position", "record_open_trade", "close_trade",
    "close_active_position", "simulate",
}
# Startup/recovery/publication and fill/mark handlers have non-order names.
EXPLICIT = {
    "backend/api/routers/market.py": {"receive_market_webhook", "analyze_live_market"},
    "backend/api/routers/intelligence_decision_api_v3.py": {"market_price_v3", "execution_pipeline_v3", "intelligence_decision_v3"},
    "backend/strategies/parameterized_strategy_runner_v2.py": {"run"},
    "backend/services/trade_lifecycle_service_v2.py": {"update_position", "_sync_open_position_state", "_sync_protection_and_oco_after_close"},
    "backend/services/account_runtime_coordinator_v2.py": {"_build", "start", "switch", "assert_published"},
    "backend/services/state_recovery_service_v2.py": {"recover_from", "reconcile_pending_from"},
    "backend/services/startup_coordinator_v2.py": {"startup_from", "startup_clean"},
    "backend/services/runtime_lifecycle_manager_v2.py": {"start_from", "start_clean", "shutdown_to"},
    "backend/services/execution_state_store_v2.py": {"restore_state", "rollback_state"},
    "backend/services/durable_execution_state_v2.py": {"durable_mutation", "account_operation", "mutation", "admission_barrier"},
    "backend/services/live_position_monitor_v2.py": {"process_price", "_persist_position"},
    "backend/services/price_feed_service_v2.py": {"process_price"},
    "backend/execution/partial_take_profit_engine_v2.py": {"apply"},
}


def source_nodes():
    def walk(nodes, prefix=""):
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                yield from walk(node.body, prefix + node.name + ".")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Nested handlers are covered by their enclosing router factory.
                yield prefix + node.name, node
    paths = sorted((ROOT / "backend").rglob("*.py"))
    paths += sorted((ROOT / "scripts").glob("*.py")) + sorted((ROOT / "tools").glob("*.py"))
    for path in paths:
        if "tests" in path.relative_to(ROOT).parts:
            continue
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        yield from ((relative, name, node) for name, node in walk(tree.body))
        body = [n for n in tree.body if not isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
        yield relative, "<module>", ast.Module(body=body, type_ignores=[])


def discover():
    builders, execution = {}, {}
    nodes = list(source_nodes())
    for path, name, node in nodes:
        calls = sorted({ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)})
        leaves = {c.rsplit(".", 1)[-1] for c in calls}
        evidence = {
            "path": path, "function": name,
            "source_sha256": hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
            "calls": calls,
        }
        ident = path + ":" + name
        if leaves & BUILDERS:
            builders[ident] = {**evidence, "construction_calls": sorted(leaves & BUILDERS)}
        if (leaves & EXECUTION or name.rsplit(".", 1)[-1] in EXECUTION
                or name.rsplit(".", 1)[-1] in EXPLICIT.get(path, set())):
            execution[ident] = {**evidence, "execution_calls": sorted(leaves & EXECUTION)}
    return builders, execution

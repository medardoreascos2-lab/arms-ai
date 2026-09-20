"""Repository-wide decision vocabulary plus reviewed non-vocabulary boundaries."""
import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VOCABULARY = {"BLOCKED", "BLOCK", "APPROVED", "ALLOW_TRADE", "BLOCK_TRADE",
              "trading_blocked", "blocking_reasons", "risk_allowed", "DO_NOT_TRADE",
              "DO_NOT_EXECUTE", "risk_approved", "sizing_approved", "EXECUTE"}
# These owners decide through booleans/exceptions/delegation rather than result vocabulary.
EXPLICIT = {
 "backend/market_data/current_candle_authority_v1.py": {"__init__", "__post_init__", "admit", "fail", "connection", "reasons", "validate_segment", "_gap_proven_closed"},
 "backend/backtesting/current_paper_runtime_v1.py": {"__init__", "advance", "_next_observation", "_validate_observation", "_can_analyze", "_reasons", "connection", "ingest", "control", "shutdown"},
 "backend/backtesting/paper_runtime_v1.py": {"__init__", "_authority_reasons", "_recover_evidence", "control", "ingest", "shutdown"},
 "backend/execution/execution_pipeline_v2.py": {"execute"},
 "backend/services/runtime_admission_v2.py": {"bind_runtime_admission", "validate_market", "require_execution_scope", "_execution_scope"},
 "backend/account/account_state_manager_v2.py": {"record_daily_pnl", "update_open_risk", "ensure_trading_day"},
 "backend/accounts/funding_firm_profile_v1.py": {"get_contract_limit"},
 "backend/services/account_switch_safety_v2.py": {"_assert_identity", "validate_signal", "_assert_quiescent", "switch"},
 "backend/services/account_runtime_coordinator_v2.py": {"assert_published", "start", "switch", "published"},
 "backend/services/durable_execution_state_v2.py": {"durable_mutation", "account_operation", "admission_barrier", "mutation", "enable", "acquire", "release"},
 "backend/services/state_recovery_service_v2.py": {"recover_from", "reconcile_pending_from"},
 "backend/services/startup_coordinator_v2.py": {"startup_from", "startup_clean"},
 "backend/services/runtime_lifecycle_manager_v2.py": {"start_from", "start_clean", "shutdown_to"},
 "backend/services/execution_state_store_v2.py": {"validate_state", "rollback_state"},
 "backend/services/economic_news_authority_v2.py": {"is_news_blocked"},
 "backend/services/runtime_spread_authority_v2.py": {"get_spread_points", "get_current_quote"},
 "backend/services/price_feed_service_v2.py": {"process_price"},
 "backend/services/market_hours_service_v2.py": {"is_market_open", "is_regular_session_open", "trading_day_for"},
 "backend/services/live_market_analysis_service.py": {"analyze", "_evaluate_confluence_v2"},
 "backend/execution/risk_manager_v2.py": {"get_contract_limit"},
 "backend/execution/position_sizing_engine_v2.py": {"calculate"},
 "backend/execution/order_validation_engine_v2.py": {"validate", "validate_candidate"},
 "backend/risk_management/position_sizing_engine.py": {"calculate", "get_contract_limit"},
 "backend/risk_management/dynamic_risk_engine.py": {"calculate"},
 "backend/risk_management/trade_validator.py": {"validate"},
 "backend/risk/risk_manager.py": {"calculate_risk_amount"},
 "backend/risk/multi_account_risk_engine_v2.py": {"get_active_risk_profile"},
 "backend/risk/signal_controller_v2.py": {"evaluate", "register_trade"},
 "backend/pipeline/risk_stage.py": {"run"},
 "backend/backtesting/risk_validation_service_v2.py": {"validate"},
 "backend/execution/signal_execution_manager.py": {"evaluate"},
 "backend/execution/trade_execution_engine.py": {"execute"},
}


def functions():
    def walk(nodes, prefix=""):
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                yield from walk(node.body, prefix + node.name + ".")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield prefix + node.name, node
                # A decorator's returned wrapper is included in its parent's evidence.
    for path in sorted((ROOT / "backend").rglob("*.py")):
        if "tests" in path.relative_to(ROOT).parts:
            continue
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for name, node in walk(tree.body):
            yield relative, name, node


def discover():
    result = {}
    for path, name, node in functions():
        strings = {n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        if not strings & VOCABULARY and node.name not in EXPLICIT.get(path, set()):
            continue
        result[path + ":" + name] = {
            "path": path, "function": name,
            "source_sha256": hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
            "inputs": ast.unparse(node.args),
            "calls": sorted({ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)}),
            "output_fields": sorted({key.value for n in ast.walk(node) if isinstance(n, ast.Dict)
                                     for key in n.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}),
        }
    return result

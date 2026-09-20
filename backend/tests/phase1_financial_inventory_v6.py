"""Reviewed financial writes, delegated mutations and reconciliation boundaries."""
import ast
import hashlib
import re
from backend.tests.phase1_risk_authority_inventory_v5 import functions

FINANCIAL = re.compile(r"fill|position|portfolio|balance|equity|pnl|journal|history|trades|orders|quantity|current_price|entry_price|commission|fee", re.I)
MUTATORS = {"append", "extend", "update", "pop", "clear", "add", "remove", "insert", "setdefault"}
# Dependency references and configuration limits do not book economic state.
REFERENCES = {"position_manager", "position_manager_v2", "position_sizing_engine", "portfolio_manager_v2",
    "portfolio_risk_engine_v2", "trade_journal_v2", "trade_history_manager", "trade_history_store",
    "signal_history_store", "journal", "live_position_monitor_v2", "realized_pnl_engine",
    "max_open_positions", "maximum_open_positions", "max_trades_per_day", "max_trades", "minimum_trades",
    "fill_market_orders_immediately", "position_filter", "position_lifecycle", "position_monitor"}
DELEGATED = {"submit_signal", "close_position", "close_partial", "update_position", "replace_active_position",
    "record_open_trade", "close_trade", "record_daily_pnl", "update_from_portfolio", "restore_state",
    "record_trade", "save_trade", "process_price"}
EXPLICIT = {
 "backend/backtesting/current_paper_runtime_v1.py": {"ingest", "record_close", "advance"},
 "backend/backtesting/paper_runtime_v1.py": {"_process"},
 "backend/backtesting/historical_accounting_v1.py": {"update_position", "record_close"},
 "backend/execution/protective_order_registry_v2.py": {"__init__", "create_protection", "complete_protection", "cancel_protection", "remove_protection"},
 "backend/execution/oco_manager_v2.py": {"__init__", "create_group", "cancel_remaining", "cancel_group", "remove_group"},
 "backend/account/account_state_manager_v2.py": {"_record_daily_pnl", "update_open_risk", "ensure_trading_day"},
 "backend/portfolio/portfolio_manager_v2.py": {"_sync_account_state", "get_total_realized_pnl", "get_total_unrealized_pnl", "restore_risk_state"},
 "backend/services/trade_lifecycle_service_v2.py": {"_sync_open_position_state", "_sync_protection_and_oco_after_close"},
 "backend/services/durable_execution_state_v2.py": {"durable_mutation", "mutation", "_checkpoint", "fail_closed"},
 "backend/services/execution_state_store_v2.py": {"_restore_records", "rollback_state", "restore_state"},
 "backend/services/state_recovery_service_v2.py": {"recover_from", "reconcile_pending_from"},
 "backend/services/pending_operation_reconciliation_v2.py": {"reconcile"},
 "backend/execution/position_manager_v2.py": {"open_position", "update_position"},
 "backend/execution/partial_take_profit_engine_v2.py": {"apply"},
 "backend/execution/realized_pnl_engine_v2.py": {"calculate"},
 "backend/execution/paper_execution_engine_v2.py": {"execute"},
 "backend/journal/trade_journal_v2.py": {"close_trade"},
 "backend/services/live_position_monitor_v2.py": {"process_price", "_persist_position"},
 "backend/services/price_feed_service_v2.py": {"process_price"},
 "backend/storage/journal_database.py": {"create_table", "save_trade"},
 "backend/execution/position_monitor.py": {"_close_and_store"},
 "backend/execution/trade_management_engine.py": {"evaluate_candle"},
 "backend/execution/execution_pipeline_v2.py": {"execute"},
 "backend/execution/execution_position_bridge_v1.py": {"execute"},
 "backend/execution/position_lifecycle_manager_v1.py": {"update"},
}


def discover():
    points = {}
    for path, name, node in functions():
        writes = set()
        for child in ast.walk(node):
            targets = []
            if isinstance(child, ast.Assign): targets = child.targets
            elif isinstance(child, (ast.AnnAssign, ast.AugAssign)): targets = [child.target]
            elif isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr in MUTATORS:
                targets = [child.func.value]
            for target in targets:
                text = ast.unparse(target)
                if not text.startswith("self.") or not FINANCIAL.search(text): continue
                if isinstance(target, ast.Attribute) and target.attr in REFERENCES: continue
                writes.add(text)
        delegated = any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                        and c.func.attr in DELEGATED for c in ast.walk(node))
        if not writes and not delegated and node.name not in EXPLICIT.get(path, set()): continue
        points[path + ":" + name] = {
            "path": path, "function": name, "input": ast.unparse(node.args),
            "source_sha256": hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
            "writes": sorted(writes),
            "calls": sorted({ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)}),
            "output_fields": sorted({k.value for n in ast.walk(node) if isinstance(n, ast.Dict)
                for k in n.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}),
        }
    return points

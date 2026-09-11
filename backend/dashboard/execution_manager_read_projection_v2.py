"""Observe orders already saved by LiveMarketAnalysisService in LiveAnalysisStore.

The stored analysis key/time, signal and prepared order establish the read-side
linkage. This is historical producer output, not a fresh execution approval.
No plans, identifiers, validation successes or prices are generated here.
"""
from datetime import datetime
import json


def _unavailable(reason):
    return {
        "status": "UNAVAILABLE", "data_status": reason, "source": None,
        "symbol": None, "direction": None, "order_type": None,
        "contracts": None, "entry": None, "stop_loss": None,
        "take_profit": None, "risk_amount": None, "approved": None,
        "order_id": None, "validation": [], "prepared_order": None,
    }


def _linked_order(analysis, plan, signal):
    """Check existing values against the signal; never re-approve or size it."""
    required = (
        "approved", "status", "decision", "execution_mode", "symbol", "side",
        "order_type", "quantity", "entry_price", "limit_price", "stop_loss",
        "take_profit", "blocking_reasons", "source_signal_status", "source_signal_decision",
    )
    if any(key not in plan for key in required):
        return "INCOMPLETE_PLAN"
    if (type(plan["approved"]) is not bool or type(signal.get("approved")) is not bool
            or type(plan["quantity"]) is not int or plan["quantity"] < 0
            or type(signal.get("contracts")) is not int
            or plan["execution_mode"] not in ("PAPER", "LIVE")
            or plan["order_type"] not in ("MARKET", "LIMIT")
            or type(plan["blocking_reasons"]) is not list
            or any(type(reason) is not str for reason in plan["blocking_reasons"])):
        return "INCOMPLETE_PLAN"
    if (plan["symbol"] != analysis["symbol"] or signal.get("symbol") != plan["symbol"]
            or str(signal.get("timeframe", "")).lower() != analysis["timeframe"].lower()
            or signal.get("direction") not in ("LONG", "SHORT")
            or plan["side"] != {"LONG": "BUY", "SHORT": "SELL"}.get(signal.get("direction"))
            or not signal.get("status") or not signal.get("decision")
            or plan["source_signal_status"] != signal["status"]
            or plan["source_signal_decision"] != signal["decision"]):
        return "UNVERIFIABLE_PROVENANCE"
    for key in ("entry_price", "stop_loss", "take_profit"):
        if key not in signal:
            return "UNVERIFIABLE_PROVENANCE"
        value = plan[key]
        if value is not None and (type(value) not in (int, float) or value <= 0):
            return "INCOMPLETE_PLAN"
        if value != signal[key]:
            return "UNVERIFIABLE_PROVENANCE"
    lifecycle = analysis.get("trade_lifecycle_v2")
    if lifecycle is not None:
        if type(lifecycle) is not dict or lifecycle.get("prepared_order") != plan:
            return "UNVERIFIABLE_PROVENANCE"
    if plan["quantity"] != signal["contracts"]:
        # The existing lifecycle can reduce quantity after risk evaluation.
        risk = lifecycle.get("risk_evaluation") if type(lifecycle) is dict else None
        if (type(risk) is not dict or risk.get("approved") is not True
                or type(risk.get("contracts")) is not int
                or plan["quantity"] != min(signal["contracts"], risk["contracts"])):
            return "UNVERIFIABLE_PROVENANCE"
    if plan["approved"]:
        if (signal["approved"] is not True or signal["status"] != "READY"
                or signal["decision"] != "SEND_SIGNAL"
                or plan["status"] != "READY_TO_SUBMIT" or plan["decision"] != "SUBMIT_ORDER"
                or plan["quantity"] <= 0 or plan["blocking_reasons"]
                or any(plan[key] is None for key in ("entry_price", "stop_loss", "take_profit"))):
            return "UNVERIFIABLE_PROVENANCE"
    elif plan["status"] != "BLOCKED" or plan["decision"] != "DO_NOT_SUBMIT":
        return "UNVERIFIABLE_PROVENANCE"
    expected_limit = plan["entry_price"] if plan["order_type"] == "LIMIT" else None
    if plan["limit_price"] is not None and type(plan["limit_price"]) not in (int, float):
        return "INCOMPLETE_PLAN"
    if plan["limit_price"] != expected_limit:
        return "UNVERIFIABLE_PROVENANCE"
    return None


def project_execution_manager(*, store, symbol=None, timeframe=None):
    if store is None:
        return _unavailable("NO_DATA")
    if (symbol is None) != (timeframe is None):
        return _unavailable("INCOMPLETE_SELECTION")
    if symbol is None:
        # The existing store has no list getter. Copy only its key index; never
        # write it or introduce a default market. Ambiguous markets need a selector.
        storage = getattr(store, "_storage", None)
        if type(storage) is not dict:
            return _unavailable("UNAVAILABLE_SOURCE")
        keys = list(storage.copy())
        if not keys:
            return _unavailable("NO_DATA")
        if len(keys) != 1:
            return _unavailable("AMBIGUOUS_SOURCE")
        key = keys[0]
        if type(key) is not tuple or len(key) != 2:
            return _unavailable("UNVERIFIABLE_PROVENANCE")
        symbol, timeframe = key
    if not all(type(value) is str and value.strip() for value in (symbol, timeframe)):
        return _unavailable("INCOMPLETE_SELECTION")
    analysis = store.get_latest(symbol=symbol, timeframe=timeframe)
    if analysis is None:
        return _unavailable("NO_DATA")
    if type(analysis) is not dict:
        return _unavailable("UNVERIFIABLE_PROVENANCE")
    plan = analysis.get("prepared_order_v2")
    if plan is None:
        return _unavailable("NO_DATA")
    signal = analysis.get("signal_v2")
    if type(plan) is not dict:
        return _unavailable("INCOMPLETE_PLAN")
    if type(signal) is not dict:
        return _unavailable("UNVERIFIABLE_PROVENANCE")
    if analysis.get("symbol") != symbol or analysis.get("timeframe") != timeframe:
        return _unavailable("UNVERIFIABLE_PROVENANCE")
    timestamp = analysis.get("analyzed_at")
    try:
        parsed = timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(timestamp)
        if parsed.utcoffset() is None:
            return _unavailable("UNVERIFIABLE_PROVENANCE")
        # Only serialize JSON data, without invoking plan builders/to_dict hooks.
        json.dumps([plan, signal], allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return _unavailable("UNVERIFIABLE_PROVENANCE")
    reason = _linked_order(analysis, plan, signal)
    if reason:
        return _unavailable(reason)
    return {
        "status": plan["status"], "data_status": "AVAILABLE",
        "source": {
            "store": "live_analysis_store", "symbol": symbol, "timeframe": timeframe,
            "analyzed_at": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            "field": "prepared_order_v2", "signal": signal,
        },
        "symbol": plan["symbol"], "direction": plan["side"],
        "order_type": plan["order_type"], "contracts": plan["quantity"],
        "entry": plan["entry_price"], "stop_loss": plan["stop_loss"],
        "take_profit": plan["take_profit"], "risk_amount": plan.get("risk_amount"),
        "approved": plan["approved"], "order_id": plan.get("order_id"),
        "validation": plan.get("validation", []), "prepared_order": plan,
    }

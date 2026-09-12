"""Pure inspection of snapshot dictionaries; never creates or restores a runtime."""
from datetime import date, datetime
from dataclasses import fields
from math import isfinite

from backend.instruments.instrument_profile_engine import InstrumentProfileEngine
from backend.journal.trade_journal_v2 import TradeJournalEntry
from backend.services.recovery_semantic_validation_v2 import validate_semantic_state


class IncompleteSnapshot(ValueError):
    pass


def at(value, *keys):
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def require(value, kind, label):
    if not isinstance(value, kind):
        raise IncompleteSnapshot("missing_or_invalid_participant:" + label)
    return value


def rows(value, key, label):
    require(value, list, label)
    ids = []
    for row in value:
        require(row, dict, label)
        identity = row.get(key)
        if not isinstance(identity, str) or not identity:
            raise IncompleteSnapshot("missing_record_identity:" + label)
        ids.append(identity)
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate_record_identity:" + label)


def numeric(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid_financial_number")
    try:
        finite = isfinite(value)
    except OverflowError as exc:
        raise ValueError("financial_number_out_of_range") from exc
    if not finite:
        raise ValueError("invalid_financial_number")
    return value


def validate_structure(state):
    """Required participants and their links, without synthesizing absent records."""
    positions = require(state.get("active_positions"), list, "lifecycle")
    protections = require(at(state, "protective_registry", "protections"), list, "protections")
    groups = require(at(state, "oco_manager", "groups"), list, "oco")
    risk = require(state.get("account_portfolio"), dict, "account_portfolio")
    account = require(risk.get("account"), dict, "account")
    financial = require(account.get("state"), dict, "financial_state")
    records = require(state.get("execution_records"), dict, "execution_records")
    paper = require(records.get("paper"), dict, "paper")
    for key in ("orders", "positions", "client_order_index"):
        require(paper.get(key), dict, "paper." + key)
    for value, key, label in (
        (positions, "position_id", "lifecycle"),
        (protections, "protection_group_id", "protections"),
        (groups, "oco_group_id", "oco"),
        (risk.get("open_positions"), "position_id", "portfolio.open"),
        (risk.get("closed_positions"), "position_id", "portfolio.closed"),
        (records.get("journal"), "trade_id", "journal"),
        (records.get("history"), "position_id", "history"),
        (records.get("protections"), "protection_group_id", "records.protections"),
        (records.get("oco_groups"), "oco_group_id", "records.oco"),
        (paper.get("fills"), "fill_id", "fills"),
    ):
        rows(value, key, label)
    if not isinstance(paper.get("account_id"), str) or not paper["account_id"]:
        raise IncompleteSnapshot("missing_paper_account_id")
    required = {
        "trading_day", "starting_balance", "account_stage", "evaluation_status",
        "profit_target", "profit_achieved", "profit_remaining", "profit_progress_percent",
        "target_reached", "balance", "equity", "peak_equity", "realized_pnl",
        "unrealized_pnl", "total_pnl", "daily_pnl", "daily_loss_used",
        "remaining_daily_loss_capacity", "drawdown", "remaining_drawdown_capacity",
        "open_positions", "closed_positions", "open_risk", "trading_blocked", "blocking_reasons",
    }
    if not required <= financial.keys() or not {"maximum_daily_loss", "maximum_total_drawdown"} <= account.keys():
        raise IncompleteSnapshot("incomplete_financial_state")
    boolean_fields = {"target_reached", "trading_blocked"}
    text_fields = {"trading_day", "account_stage", "evaluation_status"}
    nullable = {"profit_target", "profit_remaining", "profit_progress_percent", "remaining_daily_loss_capacity"}
    for key in boolean_fields:
        if type(financial[key]) is not bool:
            raise ValueError("invalid_financial_boolean")
    for key in required - boolean_fields - text_fields - {"blocking_reasons"}:
        if key in nullable and financial[key] is None:
            continue
        numeric(financial[key])
    for key in text_fields:
        if key == "account_stage" and financial[key] is None:
            continue
        if not isinstance(financial[key], str) or not financial[key]:
            raise ValueError("invalid_financial_text")
    if not isinstance(financial["blocking_reasons"], list) or any(
            not isinstance(reason, str) or not reason for reason in financial["blocking_reasons"]):
        raise ValueError("invalid_blocking_reasons")
    date.fromisoformat(financial["trading_day"])
    datetime.fromisoformat(state["captured_at"])
    for trade in records["journal"]:
        if set(trade) != {field.name for field in fields(TradeJournalEntry)}:
            raise IncompleteSnapshot("incomplete_journal_entry")
        for key in ("created_at", "closed_at"):
            if trade[key] is not None:
                datetime.fromisoformat(trade[key])
    portfolio = risk["open_positions"] + risk["closed_positions"]
    rows(portfolio, "position_id", "portfolio")
    rows(records["journal"], "position_id", "journal.position")
    if {r["position_id"] for r in portfolio} != {r["position_id"] for r in records["journal"]}:
        raise ValueError("journal_portfolio_mismatch")
    if {r["position_id"] for r in risk["closed_positions"]} != {r["position_id"] for r in records["history"]}:
        raise ValueError("history_portfolio_mismatch")
    journal = {row["position_id"]: row for row in records["journal"]}
    for position in portfolio:
        trade = journal[position["position_id"]]
        if trade["status"] != position["status"]:
            raise ValueError("journal_portfolio_status_mismatch")
        remaining = trade.get("remaining_quantity")
        if position["status"] == "OPEN" and remaining is not None and numeric(remaining) != position["quantity"]:
            raise ValueError("journal_remaining_quantity_mismatch")
    history = {row["position_id"]: row for row in records["history"]}
    for position in risk["closed_positions"]:
        if numeric(history[position["position_id"]]["realized_pnl"]) != position["realized_pnl"]:
            raise ValueError("history_portfolio_pnl_mismatch")
    for row in list(paper["orders"].values()) + paper["fills"]:
        require(row, dict, "paper_order_or_fill")
        if row.get("execution_mode") != "PAPER":
            raise ValueError("paper_record_mode_mismatch")
    for collection, status in ((positions, "OPEN"), (risk["open_positions"], "OPEN"),
                               (risk["closed_positions"], "CLOSED"), (protections, "ACTIVE"), (groups, "ACTIVE")):
        if any(row.get("status") != status for row in collection):
            raise ValueError("participant_status_mismatch")
    if len(positions) != len(protections) or len(positions) != len(groups):
        raise ValueError("missing_active_protection_or_oco")
    if [r for r in records["protections"] if r.get("status") == "ACTIVE"] != protections:
        raise ValueError("active_protection_records_mismatch")
    if [r for r in records["oco_groups"] if r.get("status") == "ACTIVE"] != groups:
        raise ValueError("active_oco_records_mismatch")
    for position in positions:
        protection = [r for r in protections if r.get("position_id") == position["position_id"]]
        oco = [r for r in groups if r.get("position_id") == position["position_id"]]
        if len(protection) != 1 or len(oco) != 1:
            raise ValueError("ambiguous_protection_link")
        protection, oco = protection[0], oco[0]
        for source, target in (("symbol", "symbol"), ("direction", "direction"), ("quantity", "quantity"),
                               ("entry_price", "entry_price"), ("stop_loss", "stop_price"),
                               ("take_profit", "take_profit_price"), ("protection_group_id", "protection_group_id")):
            if position.get(source) != protection.get(target):
                raise ValueError("protection_link_mismatch")
        if position.get("oco_group_id") != oco.get("oco_group_id"):
            raise ValueError("oco_link_mismatch")
        for key in ("stop_order_id", "take_profit_order_id"):
            if not position.get(key) or not position[key] == protection.get(key) == oco.get(key):
                raise ValueError("protective_order_link_mismatch")


def validate_financial(state):
    risk = state["account_portfolio"]
    account = risk["account"]
    f = account["state"]
    for key in ("starting_balance", "balance", "equity", "peak_equity", "realized_pnl",
                "unrealized_pnl", "total_pnl", "daily_pnl", "drawdown", "daily_loss_used"):
        numeric(f[key])
    if f["starting_balance"] <= 0 or numeric(account["maximum_total_drawdown"]) <= 0:
        raise ValueError("invalid_capital_or_drawdown_limit")
    daily_limit = account["maximum_daily_loss"]
    if daily_limit is not None and numeric(daily_limit) <= 0:
        raise ValueError("invalid_daily_limit")
    if (f["balance"] != round(f["starting_balance"] + f["realized_pnl"], 10)
            or f["equity"] != round(f["balance"] + f["unrealized_pnl"], 10)
            or f["total_pnl"] != round(f["realized_pnl"] + f["unrealized_pnl"], 10)
            or f["drawdown"] != round(max(0, f["peak_equity"] - f["equity"]), 10)):
        raise ValueError("financial_totals_mismatch")
    loss = max(0, -f["daily_pnl"])
    if f["daily_loss_used"] != loss or f["remaining_daily_loss_capacity"] != (None if daily_limit is None else max(0, daily_limit - loss)):
        raise ValueError("daily_loss_mismatch")
    reasons = require(f["blocking_reasons"], list, "blocking_reasons")
    if not isinstance(f["trading_blocked"], bool):
        raise ValueError("invalid_trading_block")
    if ((reasons and not f["trading_blocked"])
            or (daily_limit is not None and loss >= daily_limit and "daily_loss_limit_reached" not in reasons)
            or (f["drawdown"] >= account["maximum_total_drawdown"] and "maximum_total_drawdown_reached" not in reasons)):
        raise ValueError("risk_block_mismatch")
    if f["open_positions"] != len(risk["open_positions"]) or f["closed_positions"] != len(risk["closed_positions"]):
        raise ValueError("portfolio_counts_mismatch")
    positions = risk["open_positions"] + risk["closed_positions"]
    realized = round(sum(numeric(row["realized_pnl"]) for row in positions), 10)
    unrealized = 0.0
    for row in risk["open_positions"]:
        if row["direction"] not in {"LONG", "SHORT"}:
            raise ValueError("invalid_position_direction")
        unrealized += ((1 if row["direction"] == "LONG" else -1)
                       * (numeric(row["current_price"]) - numeric(row["entry_price"]))
                       * numeric(row["quantity"]) * numeric(row["point_value"]))
    if f["realized_pnl"] != realized or f["unrealized_pnl"] != round(unrealized, 10):
        raise ValueError("account_portfolio_pnl_mismatch")
    instruments = InstrumentProfileEngine()
    validate_semantic_state(state, point_value_for=lambda *, symbol: instruments.get_profile(symbol=symbol)["point_value"])

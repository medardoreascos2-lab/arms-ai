"""Semantic PAPER evidence validation shared by COMMITTED and PENDING recovery.

No replay, inference of missing execution, or accounting mutations occur here.
PAPER terminal positions are the existing full-close execution record; partial
closes have fills. Both are required and valued, never manufactured on recovery.
"""
from datetime import datetime
from math import isfinite

from backend.services.market_hours_service_v2 import MarketHoursServiceV2


def number(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("Invalid economic number.")
    if positive and value <= 0:
        raise ValueError("Economic quantity/price must be positive.")
    return float(value)


def trading_day(value):
    if not isinstance(value, str):
        raise ValueError("Missing execution timestamp.")
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        raise ValueError("Execution timestamp must have a timezone.")
    return MarketHoursServiceV2.trading_day_for(timestamp).isoformat()


def validate_semantic_state(state, *, point_value_for):
    try:
        _validate(state, point_value_for)
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError("Incomplete semantic execution evidence.") from exc


def _validate(state, point_value_for):
    after = state["execution_records"]
    risk_after = state["account_portfolio"]
    if not after or risk_after is None or after["journal"] is None or after["paper"] is None:
        raise ValueError("Recovery requires canonical PAPER, account, portfolio and journal evidence.")
    paper = after["paper"]
    journal = {row["position_id"]: row for row in after["journal"]}
    portfolio = risk_after["open_positions"] + risk_after["closed_positions"]
    if (len(portfolio) != len(paper["positions"])
            or {row.get("broker_position_id") for row in portfolio} != set(paper["positions"])):
        raise ValueError("PAPER/portfolio identity mismatch.")
    for order_id, order in paper["orders"].items():
        if not isinstance(order_id, str) or not order_id or order_id != order["order_id"]:
            raise ValueError("Order identity mismatch.")
        number(order["quantity"], positive=True)
        if order["status"] not in {"FILLED", "PARTIALLY_FILLED", "SUBMITTED", "REJECTED", "CANCELLED"}:
            raise ValueError("Unsupported PAPER order status.")
        client_id = order.get("client_order_id")
        if client_id and paper["client_order_index"].get(client_id) != order_id:
            raise ValueError("PAPER client-order identity mismatch.")
        if order["status"] in {"FILLED", "PARTIALLY_FILLED"} and order.get("position_id") not in paper["positions"]:
            raise ValueError("Executed order lacks PAPER position.")
    for client_id, order_id in paper["client_order_index"].items():
        if paper["orders"][order_id].get("client_order_id") != client_id:
            raise ValueError("PAPER client-order index contradicts order.")
    position_orders = {row["order_id"] for row in paper["positions"].values()}
    if len(position_orders) != len(paper["positions"]):
        raise ValueError("Multiple positions claim the same entry order.")
    for fill in paper["fills"]:
        if not isinstance(fill.get("fill_id"), str) or not fill["fill_id"]:
            raise ValueError("Missing fill identity.")
        if fill["order_id"] not in position_orders:
            raise ValueError("Fill lacks corresponding position/accounting evidence.")
        if any(isinstance(fill.get(key), bool) or not isinstance(fill.get(key), (int, float))
               or not isfinite(fill[key]) or fill[key] <= 0 for key in ("quantity", "filled_price")):
            raise ValueError("Invalid fill quantity or price.")
        if fill.get("fill_type") not in {None, "PARTIAL_CLOSE"}:
            raise ValueError("Unsupported fill evidence.")
    lifecycle = {row["position_id"]: row for row in state["active_positions"]}
    if set(lifecycle) != {row["position_id"] for row in portfolio if row["status"] == "OPEN"}:
        raise ValueError("Active lifecycle/PAPER exposure mismatch.")
    economic_total = economic_daily = 0.
    account_day = risk_after["account"]["state"]["trading_day"]
    for position in portfolio:
        if position["direction"] not in {"LONG", "SHORT"} or position.get("execution_mode") != "PAPER":
            raise ValueError("Invalid PAPER position direction/mode.")
        broker = paper["positions"][position["broker_position_id"]]
        trade = journal[position["position_id"]]
        if broker.get("execution_mode") != "PAPER" or not isinstance(trade.get("trade_id"), str) or not trade["trade_id"]:
            raise ValueError("Invalid broker/journal identity or mode.")
        order = paper["orders"][broker["order_id"]]
        entries = [row for row in paper["fills"] if row["order_id"] == broker["order_id"]
                   and row.get("fill_type") != "PARTIAL_CLOSE"]
        partials = [row for row in paper["fills"] if row["order_id"] == broker["order_id"]
                    and row.get("fill_type") == "PARTIAL_CLOSE"]
        if len(entries) != 1:
            raise ValueError("Entry fill is not uniquely demonstrated.")
        entry = entries[0]
        if (broker["position_id"] != position["broker_position_id"]
                or broker["status"] != position["status"]
                or position["order_id"] != broker["order_id"]
                or order.get("position_id") != broker["position_id"]
                or entry["quantity"] != trade["contracts"]
                or entry["filled_price"] != order["filled_price"]
                or entry["filled_price"] != position["entry_price"]
                or trade["entry"] != position["entry_price"]
                or broker["entry_price"] != position["entry_price"]
                or entry["side"] != order["side"] or entry["side"] != broker["side"]
                or trade["direction"] != position["direction"]
                or entry["side"] != ("BUY" if position["direction"] == "LONG" else "SELL")
                or len({entry["symbol"], order["symbol"], broker["symbol"],
                        trade["symbol"], position["symbol"]}) != 1):
            raise ValueError("Broker, fill and journal evidence contradict each other.")
        if not ((order["status"] == "FILLED" and entry["quantity"] == order["quantity"])
                or (order["status"] == "PARTIALLY_FILLED" and 0 < entry["quantity"] < order["quantity"])):
            raise ValueError("Order fill status contradicts demonstrated quantity.")
        remaining = round(entry["quantity"] - sum(row["quantity"] for row in partials), 10)
        # PAPER full closes retain the last open quantity in both terminal
        # records. Closed status must not exempt contradictory partial fills.
        if (remaining <= 0 or remaining != position["quantity"]
                or remaining != broker["quantity"]):
            raise ValueError("Remaining fill quantity contradicts exposure.")
        if any(row["quantity"] <= 0 or row.get("position_id") != broker["position_id"] for row in partials):
            raise ValueError("Invalid partial fill evidence.")
        if any(row["symbol"] != broker["symbol"] or row["side"] != ("SELL" if broker["side"] == "BUY" else "BUY") for row in partials):
            raise ValueError("Partial fill direction or symbol mismatch.")
        if position["status"] == "CLOSED" and (
                broker.get("exit_price") != position.get("exit_price")
                or trade.get("exit_price") != position.get("exit_price")):
            raise ValueError("Closed position exit evidence contradicts accounting.")

        point_value = number(position["point_value"], positive=True)
        if point_value != number(point_value_for(symbol=position["symbol"]), positive=True):
            raise ValueError("Execution point value differs from the configured instrument.")
        sign = 1 if position["direction"] == "LONG" else -1
        entry_price = number(entry["filled_price"], positive=True)
        events = []
        entry_day = trading_day(entry["filled_at"])
        if entry_day > account_day:
            raise ValueError("Entry occurs after account trading day.")
        last_execution = datetime.fromisoformat(entry["filled_at"])
        for fill in partials:
            fill_day = trading_day(fill["filled_at"])
            timestamp = datetime.fromisoformat(fill["filled_at"])
            if timestamp < last_execution:
                raise ValueError("Partial execution precedes its entry/previous fill.")
            last_execution = timestamp
            events.append((fill_day, round(
                sign * (fill["filled_price"] - entry_price) * fill["quantity"] * point_value, 10)))
        if position["status"] == "CLOSED":
            exit_price = number(broker["exit_price"], positive=True)
            if not broker.get("close_reason"):
                raise ValueError("Missing terminal PAPER close evidence.")
            close_day = trading_day(broker["closed_at"])
            if datetime.fromisoformat(broker["closed_at"]) < last_execution:
                raise ValueError("Terminal close precedes a demonstrated fill.")
            events.append((close_day, round(
                sign * (exit_price - entry_price) * remaining * point_value, 10)))
            history = {row["position_id"]: row for row in after["history"]}[position["position_id"]]
            for field in ("symbol", "direction", "entry_price", "exit_price", "quantity", "point_value"):
                if history.get(field) != position.get(field):
                    raise ValueError("Closed history contradicts execution evidence.")
        expected = round(sum(pnl for _, pnl in events), 10)
        if number(position["realized_pnl"]) != expected or number(trade["pnl"]) != expected:
            raise ValueError("Stored PnL contradicts economic execution evidence.")
        for day, _ in events:
            if day < entry_day or day > risk_after["account"]["state"]["trading_day"]:
                raise ValueError("Execution date contradicts account trading day.")
        economic_total += expected
        economic_daily += sum(pnl for day, pnl in events if day == account_day)
        if position["status"] == "OPEN":
            active = lifecycle[position["position_id"]]
            for field in ("broker_position_id", "order_id", "symbol", "direction", "quantity",
                          "entry_price", "point_value", "realized_pnl", "stop_loss", "take_profit",
                          "protection_group_id", "oco_group_id", "stop_order_id", "take_profit_order_id"):
                if active.get(field) != position.get(field):
                    raise ValueError("Active lifecycle/portfolio mismatch: " + field)
            for field in ("stop_loss", "take_profit"):
                if not (broker.get(field) == order.get(field) == active.get(field)):
                    raise ValueError("PAPER protection price contradicts lifecycle/registry.")

    account = risk_after["account"]["state"]
    if number(account["realized_pnl"]) != round(economic_total, 10):
        raise ValueError("Account realized PnL contradicts execution evidence.")
    # Explicit pre-existing account API adjustments are risk inputs, not fills.
    # They cannot be inferred from a mismatching saved daily balance.
    adjustment_total = 0.
    for adjustment in risk_after["account"].get("daily_pnl_adjustments", []):
        if adjustment["trading_day"] != account_day or trading_day(adjustment["recorded_at"]) != account_day:
            raise ValueError("Daily risk adjustment date mismatch.")
        adjustment_total += number(adjustment["amount"])
    if number(account["daily_pnl"]) != round(economic_daily + adjustment_total, 10):
        raise ValueError("Daily PnL lacks dated execution/adjustment evidence.")

"""Pre-submit PAPER identity reservation never writes financial evidence."""
from unittest.mock import Mock

from backend.connectors.paper_broker_connector_v2 import PaperBrokerConnectorV2
from backend.execution.paper_execution_engine_v2 import PaperExecutionEngineV2
from backend.tests.test_paper_execution_engine_v2 import build_valid_order


def broker():
    owner = PaperBrokerConnectorV2(execution_engine=PaperExecutionEngineV2(
        fill_market_orders_immediately=True,slippage_points=.25))
    owner.connect()
    return owner


def test_preflight_rejection_has_no_order_fill_or_position():
    owner = broker()
    order = build_valid_order()
    order["approved"] = False
    result = owner.reserve_paper_submission(prepared_order=order)
    assert result["accepted"] is False
    assert owner.get_orders() == []
    assert owner.get_fills() == []
    assert owner.get_positions() == []


def test_exhausted_generated_identity_collision_rejects_before_submit(monkeypatch):
    owner = broker()
    order = build_valid_order()
    original = owner.execution_engine.execute
    def collision(*,prepared_order):
        result = original(prepared_order=prepared_order)
        result["order_id"] = "prior-financial-order"
        return result
    monkeypatch.setattr(owner.execution_engine,"execute",collision)
    monkeypatch.setattr("backend.connectors.paper_broker_connector_v2.uuid4",
        lambda:"prior-financial-order")
    submit = Mock(wraps=owner.submit_order)
    monkeypatch.setattr(owner,"submit_order",submit)
    result = owner.reserve_paper_submission(prepared_order=order,
        forbidden_order_ids=("prior-financial-order",))
    assert result == dict(accepted=False,reason="PAPER_ORDER_ID_RESERVATION_FAILED")
    assert submit.call_count == 0
    assert owner.get_orders() == owner.get_fills() == owner.get_positions() == []


def test_reserved_ids_are_unique_before_ledger_mutation(monkeypatch):
    owner = broker()
    order = build_valid_order()
    original = owner.execution_engine.execute
    def collision(*,prepared_order):
        result = original(prepared_order=prepared_order)
        result["order_id"] = "prior-financial-order"
        return result
    monkeypatch.setattr(owner.execution_engine,"execute",collision)
    reservation = owner.reserve_paper_submission(prepared_order=order,
        forbidden_order_ids=("prior-financial-order",))
    assert reservation["accepted"] is True
    assert owner.get_orders() == owner.get_fills() == owner.get_positions() == []
    result = owner.submit_order(prepared_order=order,reservation=reservation["reservation"])
    assert result["order_id"] != "prior-financial-order"
    assert result["status"] == "FILLED"
    assert len(owner.get_orders()) == len(owner.get_fills()) == len(owner.get_positions()) == 1

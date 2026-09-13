from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from backend.api import dashboard_live_api_v2
from backend.api import dashboard_widgets_api_v2
from backend.api.routers import execution_approval_api_v2
from backend.api.routers import execution_manager_api_v2
from backend.api.routers import execution_simulator_api_v2
from backend.api.routers import intelligence_decision_api_v3
from backend.dashboard.dashboard_auto_refresh_engine_v2 import (
    DashboardAutoRefreshEngineV2,
)
from backend.dashboard.dashboard_refresh_service_v2 import (
    DashboardRefreshServiceV2,
)
from backend.dashboard.dashboard_websocket_broadcaster_v2 import (
    DashboardWebSocketBroadcasterV2,
)


class ExecutionSideEffectProbe:
    def __init__(self):
        self.submit_order_calls = 0
        self.fill_calls = 0
        self.position_mutation_calls = 0
        self.lifecycle_mutation_calls = 0
        self.account_identity_mutation_calls = 0

    def submit_order(self, *args, **kwargs):
        self.submit_order_calls += 1
        raise AssertionError(
            "A dashboard read attempted to submit an order."
        )

    def create_fill(self, *args, **kwargs):
        self.fill_calls += 1
        raise AssertionError(
            "A dashboard read attempted to create a fill."
        )

    def mutate_position(self, *args, **kwargs):
        self.position_mutation_calls += 1
        raise AssertionError(
            "A dashboard read attempted to mutate a position."
        )

    def mutate_lifecycle(self, *args, **kwargs):
        self.lifecycle_mutation_calls += 1
        raise AssertionError(
            "A dashboard read attempted to mutate lifecycle state."
        )

    def mutate_account_identity(self, *args, **kwargs):
        self.account_identity_mutation_calls += 1
        raise AssertionError(
            "A dashboard read attempted to mutate account identity."
        )

    def assert_untouched(self):
        assert self.submit_order_calls == 0
        assert self.fill_calls == 0
        assert self.position_mutation_calls == 0
        assert self.lifecycle_mutation_calls == 0
        assert self.account_identity_mutation_calls == 0


class ReadOnlyLifecycle:
    def __init__(self, probe: ExecutionSideEffectProbe):
        self.probe = probe
        self.positions = [
            {
                "position_id": "position-1",
                "symbol": "NQ",
                "direction": "LONG",
                "status": "OPEN",
            }
        ]

    def get_active_positions(self):
        return deepcopy(self.positions)

    def get_trades(self):
        return [
            {
                "trade_id": "trade-1",
                "position_id": "position-1",
                "symbol": "NQ",
                "direction": "LONG",
                "status": "OPEN",
            }
        ]


class ReadOnlyPortfolio:
    def __init__(self):
        self.summary = {
            "account": "PAPER-1",
            "balance": 100000.0,
            "positions": 1,
        }

    def get_summary(self):
        return deepcopy(self.summary)


class ReadOnlyJournal:
    def __init__(self):
        self.trades = [
            {
                "trade_id": "trade-1",
                "position_id": "position-1",
                "symbol": "NQ",
                "direction": "LONG",
                "status": "OPEN",
            }
        ]

    def get_trades(self):
        return deepcopy(self.trades)


class ReadOnlyAccountConfig:
    def __init__(self):
        self.account_name = "PAPER-1"

    def get_active_account(self):
        return SimpleNamespace(
            risk_percent=1.0,
            account_size=100000.0,
        )


class ReadOnlyExecutionPipeline:
    def __init__(self, probe: ExecutionSideEffectProbe):
        self.probe = probe
        self.journal = ReadOnlyJournal()

    def execute(self, *args, **kwargs):
        self.probe.lifecycle_mutation_calls += 1
        raise AssertionError(
            "A dashboard read attempted to execute the pipeline."
        )


class FakeRequest:
    def __init__(self, **state):
        self.app = SimpleNamespace(
            state=SimpleNamespace(**state)
        )


class FakeExecutionApprovalEngine:
    def __init__(self, probe: ExecutionSideEffectProbe):
        self.probe = probe
        self.validate_calls = 0

    def validate_execution(self, **kwargs):
        self.validate_calls += 1
        return SimpleNamespace(
            status="VALID",
            symbol=kwargs["symbol"],
            direction=kwargs["direction"],
            entry=kwargs["entry"],
            stop_loss=kwargs["stop_loss"],
            take_profit=kwargs["take_profit"],
            risk_amount=kwargs["risk_amount"],
            confidence=kwargs["confidence"],
            validation={"approved": True},
        )


class FakeExecutionSimulatorEngine:
    def __init__(self, probe: ExecutionSideEffectProbe):
        self.probe = probe
        self.simulate_calls = 0

    def simulate_execution(self, **kwargs):
        self.simulate_calls += 1
        return SimpleNamespace(
            status="SIMULATED",
            symbol=kwargs["symbol"],
            direction=kwargs["direction"],
            entry=kwargs["entry"],
            stop_loss=kwargs["stop_loss"],
            take_profit=kwargs["take_profit"],
            risk_points=50,
            reward_points=150,
            risk_reward=3.0,
            contracts=1,
            max_loss=500,
            expected_profit=1500,
        )


def test_execution_dashboard_reads_do_not_execute_or_mutate_state(
    monkeypatch,
):
    probe = ExecutionSideEffectProbe()
    approval_engine = FakeExecutionApprovalEngine(probe)
    simulator_engine = FakeExecutionSimulatorEngine(probe)

    monkeypatch.setattr(
        execution_approval_api_v2,
        "execution_engine",
        approval_engine,
    )
    monkeypatch.setattr(
        execution_simulator_api_v2,
        "engine",
        simulator_engine,
    )

    request = FakeRequest(
        active_maximum_daily_loss=1000.0,
    )

    approval_result = (
        execution_approval_api_v2.execution_approval_dashboard(
            request
        )
    )
    simulator_result = (
        execution_simulator_api_v2.execution_simulator_dashboard()
    )

    assert approval_result["status"] == "VALID"
    assert simulator_result["status"] == "SIMULATED"
    assert approval_engine.validate_calls == 1
    assert simulator_engine.simulate_calls == 1
    probe.assert_untouched()


def test_execution_manager_dashboard_only_projects_existing_data(
    monkeypatch,
):
    probe = ExecutionSideEffectProbe()
    store = {
        "prepared_order": {
            "symbol": "NQ",
            "direction": "BUY",
        }
    }
    state_before = deepcopy(store)

    def fake_projection(*, store, symbol, timeframe):
        assert store == state_before
        assert symbol == "NQ"
        assert timeframe == "5m"
        return {
            "status": "AVAILABLE",
            "prepared_order": deepcopy(store["prepared_order"]),
        }

    monkeypatch.setattr(
        execution_manager_api_v2,
        "project_execution_manager",
        fake_projection,
    )

    request = FakeRequest(
        live_analysis_store=store,
    )

    result = execution_manager_api_v2.execution_manager_dashboard(
        request=request,
        symbol="NQ",
        timeframe="5m",
    )

    assert result["status"] == "AVAILABLE"
    assert store == state_before
    probe.assert_untouched()


def test_intelligence_dashboard_reads_do_not_execute_or_mutate_state(
    monkeypatch,
):
    probe = ExecutionSideEffectProbe()
    lifecycle = ReadOnlyLifecycle(probe)
    portfolio = ReadOnlyPortfolio()
    journal = ReadOnlyJournal()
    account_config = ReadOnlyAccountConfig()
    pipeline = ReadOnlyExecutionPipeline(probe)

    class FakeTechnicalEngine:
        def analyze(self, **kwargs):
            return {"technical": "BULLISH"}

    class FakeStructureEngine:
        def analyze(self, **kwargs):
            return {"structure": "CONFIRMED"}

    class FakeRiskEngine:
        def analyze(self, **kwargs):
            return {"risk": "APPROVED"}

    class FakeProvider:
        def collect(self, **kwargs):
            return {"confidence": 0.95}

    class FakeOrchestrator:
        def analyze(self, **kwargs):
            return SimpleNamespace(
                symbol="NQ",
                direction="BUY",
                entry=23500,
                stop_loss=23450,
                take_profit=23650,
                final_confidence=95,
                quality="A+",
                decision="APPROVED",
                execution_status="READY",
                risk_allowed=True,
                risk_score=95,
                sources=["technical", "structure", "risk"],
                reasoning=["all checks passed"],
                recommendations=[],
            )

    class FakeTradeExecutionIntelligence:
        def analyze(self, **kwargs):
            return SimpleNamespace(
                entry=23500,
                stop_loss=23450,
                take_profit=23650,
                risk_amount=500,
                reward_amount=1500,
                risk_reward_ratio=3.0,
                contracts=1,
                approved=True,
            )

    class FakeExecutionPipeline:
        def __init__(self):
            self.journal = journal

        def execute(self, *args, **kwargs):
            probe.lifecycle_mutation_calls += 1
            raise AssertionError(
                "The intelligence dashboard attempted execution."
            )

    monkeypatch.setattr(
        intelligence_decision_api_v3,
        "technical_engine",
        FakeTechnicalEngine(),
    )
    monkeypatch.setattr(
        intelligence_decision_api_v3,
        "structure_engine",
        FakeStructureEngine(),
    )
    monkeypatch.setattr(
        intelligence_decision_api_v3,
        "risk_engine",
        FakeRiskEngine(),
    )
    monkeypatch.setattr(
        intelligence_decision_api_v3,
        "provider",
        FakeProvider(),
    )
    monkeypatch.setattr(
        intelligence_decision_api_v3,
        "orchestrator",
        FakeOrchestrator(),
    )
    monkeypatch.setattr(
        intelligence_decision_api_v3,
        "execution_engine",
        FakeTradeExecutionIntelligence(),
    )

    state = {
        "account_config_manager_v2": account_config,
        "trade_lifecycle_service_v2": lifecycle,
        "portfolio_manager_v2": portfolio,
        "trade_journal_v2": journal,
        "execution_pipeline_v3": FakeExecutionPipeline(),
    }
    request = FakeRequest(**state)
    state_before = deepcopy(state)

    decision_result = (
        intelligence_decision_api_v3.intelligence_decision_v3(
            request
        )
    )
    position_result = (
        intelligence_decision_api_v3.position_debug_v3(request)
    )
    journal_result = (
        intelligence_decision_api_v3.journal_debug_v3(request)
    )
    pipeline_result = (
        intelligence_decision_api_v3.execution_pipeline_v3(request)
    )

    assert decision_result["execution_status"] == "READY"
    assert position_result["active_positions"][0]["position_id"] == (
        "position-1"
    )
    assert journal_result["total"] == 1
    assert pipeline_result["status"] == "AVAILABLE"

    assert lifecycle.positions == state_before[
        "trade_lifecycle_service_v2"
    ].positions
    assert portfolio.summary == state_before[
        "portfolio_manager_v2"
    ].summary
    assert journal.trades == state_before[
        "trade_journal_v2"
    ].trades
    assert account_config.account_name == state_before[
        "account_config_manager_v2"
    ].account_name

    probe.assert_untouched()


def test_dashboard_live_and_widgets_are_observational():
    probe = ExecutionSideEffectProbe()
    snapshot = {
        "dashboard_status": "READY",
        "account": "PAPER-1",
    }
    widgets = {
        "status": "READY",
        "widget_count": 1,
        "widgets": {"risk": {"status": "OK"}},
    }

    class LiveDataService:
        def get_snapshot(self):
            return deepcopy(snapshot)

    class WidgetRegistry:
        def render_all(self):
            return deepcopy(widgets)

    live_router = dashboard_live_api_v2.create_dashboard_live_router_v2(
        live_data_service_v2=LiveDataService()
    )
    widget_router = (
        dashboard_widgets_api_v2.create_dashboard_widgets_router_v2(
            widget_registry_v2=WidgetRegistry()
        )
    )

    live_route = next(
        route.endpoint
        for route in live_router.routes
        if route.path == "/api/v2/dashboard/live"
    )
    widget_route = next(
        route.endpoint
        for route in widget_router.routes
        if route.path == "/api/v2/dashboard/widgets"
    )

    snapshot_before = deepcopy(snapshot)
    widgets_before = deepcopy(widgets)

    assert live_route() == snapshot_before
    assert widget_route() == widgets_before
    assert snapshot == snapshot_before
    assert widgets == widgets_before
    probe.assert_untouched()


def test_dashboard_refresh_and_websocket_broadcast_do_not_execute():
    probe = ExecutionSideEffectProbe()
    snapshot = {
        "dashboard_status": "READY",
        "account": "PAPER-1",
    }
    widgets = {
        "status": "READY",
        "widget_count": 1,
        "widgets": {},
    }

    class LiveDataService:
        def get_snapshot(self):
            return deepcopy(snapshot)

    class WidgetRegistry:
        def render_all(self):
            return deepcopy(widgets)

    class EventBus:
        def __init__(self):
            self.events = []

        def publish(self, *, event_type, payload):
            self.events.append(
                {
                    "event_type": event_type,
                    "payload": deepcopy(payload),
                }
            )
            return {"published": True}

    class EventDispatcher:
        def register(self):
            return {"subscription_count": 1}

    class WebSocketHub:
        def __init__(self):
            self.payloads = []

        async def broadcast(self, *, payload):
            self.payloads.append(deepcopy(payload))
            return {
                "broadcasted": True,
                "messages_sent": 1,
            }

    refresh_service = DashboardRefreshServiceV2(
        live_data_service_v2=LiveDataService(),
        widget_registry_v2=WidgetRegistry(),
    )
    event_bus = EventBus()
    auto_refresh = DashboardAutoRefreshEngineV2(
        event_bus_v2=event_bus,
        event_dispatcher_v2=EventDispatcher(),
        refresh_service_v2=refresh_service,
    )

    start_result = auto_refresh.start()
    publish_result = auto_refresh.publish_event(
        event_type="dashboard_refresh",
        payload={"source": "test"},
    )

    websocket_hub = WebSocketHub()
    broadcaster = DashboardWebSocketBroadcasterV2(
        refresh_service_v2=refresh_service,
        websocket_hub_v2=websocket_hub,
    )

    import asyncio

    broadcast_result = asyncio.run(
        broadcaster.broadcast_update(
            reason="dashboard_refresh",
            event={
                "event_type": "dashboard_refresh",
                "payload": {},
            },
        )
    )

    assert start_result["started"] is True
    assert start_result["initial_refresh"] is True
    assert publish_result["published"] is True
    assert broadcast_result["broadcasted"] is True
    assert len(websocket_hub.payloads) == 1
    assert refresh_service.get_cached_snapshot() == snapshot
    assert refresh_service.get_cached_widgets() == widgets
    probe.assert_untouched()

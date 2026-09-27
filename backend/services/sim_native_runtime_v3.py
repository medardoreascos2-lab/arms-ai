"""Explicit, execution-disabled SIM_NATIVE composition.

Uses canonical profile/gate/financial owners in a fresh account namespace.
It neither changes the PAPER runtime nor implements a native transport. The
Account bridge remains the sole future native submit owner.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from uuid import uuid4

from backend.accounts.sim_native_account_v3 import SimNativeAccountV3, digest
from backend.connectors.ninjatrader_sim_broker_connector_v2 import NinjaTraderSimBrokerConnectorV2
from backend.execution.execution_manager_v2 import ExecutionManagerV2
from backend.execution.paper_execution_engine_v2 import PaperExecutionEngineV2
from backend.services.durable_execution_state_v2 import AccountAdmissionRejected
from backend.services.sim_admission_envelope_v3 import NativeAdmissionAuthorityV3, utc_us
from backend.services.sim_native_financial_checkpoint_v3 import NativeSimFinancialCheckpointV3


class DisabledNativeSimConnectorV3(NinjaTraderSimBrokerConnectorV2):
    def __init__(self, binding):
        self.sim_native_account_binding = binding
        self._connected = False

    def connect(self):
        return {"connected": False, "status": "NATIVE_SUBMIT_DISABLED", "execution_domain": "SIM_NATIVE"}

    def disconnect(self):
        return self.connect()

    @staticmethod
    def _disabled(*args, **kwargs):
        raise RuntimeError("native SIM transport is disabled; Account bridge owns execution")

    submit_order = modify_order = cancel_order = close_position = close_partial = _disabled
    get_positions = get_orders = get_fills = get_account = health_check = reconcile_order = _disabled


class NativeAdmissionManagerV3(ExecutionManagerV2):
    """Shares contract-limit policy but cannot prepare an executable order."""
    def prepare_order(self, **kwargs):
        raise AccountAdmissionRejected("native executable preparation remains disabled")


class DisabledPaperEngineV3(PaperExecutionEngineV2):
    """Legacy lifecycle constructor dependency with no PAPER execution authority."""
    def execute(self, **kwargs):
        raise AccountAdmissionRejected("PAPER execution prohibited in SIM_NATIVE")


class NativeAccountSafetyV3:
    def __init__(self, *, binding, lifecycle, manager, settings):
        self.binding, self.lifecycle, self.manager = binding, lifecycle, manager
        self.settings = settings
        self.policy_digest = digest(asdict(settings))
        self._guard_owners = (lifecycle.risk_manager_v2, lifecycle.exposure_manager_v2,
            lifecycle.portfolio_risk_engine_v2, lifecycle.order_validation_engine_v2, lifecycle.execution_risk_gate_v1)
        self._approved_rules = self._rules()

    def _rules(self):
        lifecycle = self.lifecycle
        owners = {
            "risk": (lifecycle.risk_manager_v2, ("maximum_daily_loss", "maximum_total_drawdown", "maximum_contracts", "maximum_open_positions")),
            "exposure": (lifecycle.exposure_manager_v2, ("maximum_total_open_risk", "maximum_symbol_open_risk", "maximum_total_contracts", "maximum_symbol_contracts")),
            "portfolio": (lifecycle.portfolio_risk_engine_v2, ("maximum_total_open_risk", "maximum_floating_loss", "maximum_long_risk", "maximum_short_risk", "maximum_symbol_risk")),
            "order": (lifecycle.order_validation_engine_v2, ("minimum_reward_risk_ratio", "minimum_stop_points", "maximum_stop_points")),
            "account": (lifecycle.portfolio_manager_v2.account_state_manager_v2, ("maximum_daily_loss", "maximum_total_drawdown", "profit_target", "account_stage")),
            "runtime": (lifecycle.runtime_admission_v2.settings, ("maximum_quote_age_seconds", "maximum_signal_age_seconds", "maximum_spread_points",
                "minimum_a_plus_probability", "minimum_a_plus_confluence_score", "maximum_open_positions")),
        }
        return {name: {field: getattr(owner, field, None) for field in fields} for name, (owner, fields) in owners.items()}

    def _assert_identity(self):
        binding, lifecycle = self.binding, self.lifecycle
        binding.manager()
        if (self.manager.get_active_account_name() != binding.risk_profile_id
                or digest(asdict(self.manager.get_active_account())) != binding.risk_profile_digest
                or digest(asdict(self.settings)) != self.policy_digest
                or type(lifecycle.broker_connector_v2) is not DisabledNativeSimConnectorV3
                or self._rules() != self._approved_rules
                or any(current is not original for current, original in zip(
                    (lifecycle.risk_manager_v2, lifecycle.exposure_manager_v2, lifecycle.portfolio_risk_engine_v2,
                     lifecycle.order_validation_engine_v2, lifecycle.execution_risk_gate_v1), self._guard_owners))):
            raise AccountAdmissionRejected("native account risk authority changed")
        for owner in (lifecycle, lifecycle.broker_connector_v2, lifecycle.portfolio_manager_v2,
                      lifecycle.trade_journal_v2, lifecycle.portfolio_manager_v2.account_state_manager_v2):
            if getattr(owner, "sim_native_account_binding", None) is not binding:
                raise AccountAdmissionRejected("native account participant mismatch")

    def validate_signal(self, *, signal, risk_context):
        self._assert_identity()
        expected = {"account_id": self.binding.backend_account_id, "profile_name": self.binding.risk_profile_id,
                    "runtime_generation": self.binding.runtime_generation, "execution_domain": "SIM_NATIVE"}
        for source in (signal, risk_context):
            if not isinstance(source, dict) or any(type(source.get(k)) is not type(v) or source.get(k) != v for k,v in expected.items()):
                raise AccountAdmissionRejected("native signal account/domain/generation mismatch")
        if (risk_context.get("risk_percent") != self.manager.get_active_account().risk_percent
                or risk_context.get("account_balance") != self.lifecycle.portfolio_manager_v2.get_available_balance()):
            raise AccountAdmissionRejected("native signal risk authority mismatch")
        state = self.lifecycle.portfolio_manager_v2.account_state_manager_v2.get_state()
        if risk_context.get("daily_pnl") != state["daily_pnl"] or risk_context.get("total_drawdown") != state["drawdown"]:
            raise AccountAdmissionRejected("native signal account-state mismatch")


class NativeAdmissionProducerV3:
    """Called only at the canonical lifecycle's post-gate admission boundary."""
    def __init__(self, *, store, binding, key, runtime_evidence, protection_timeout_us, recovery_timeout_us):
        if (not callable(runtime_evidence) or type(protection_timeout_us) is not int or protection_timeout_us <= 0
                or type(recovery_timeout_us) is not int or recovery_timeout_us <= protection_timeout_us):
            raise ValueError("explicit runtime evidence and bounded recovery policy required")
        self.store, self.binding = store, binding
        self.runtime_evidence = runtime_evidence
        self.protection_timeout_us, self.recovery_timeout_us = protection_timeout_us, recovery_timeout_us
        lifecycle = store.trade_lifecycle_service
        self.authority = NativeAdmissionAuthorityV3(key=key, account_binding=binding,
            execution_scope_guard=lifecycle.runtime_admission_v2.require_execution_scope)

    def risk_version(self):
        """The same policy identity used for configuration and admission."""
        self.store._durability.account_switch_safety._assert_identity()
        return digest({"profile": self.binding.risk_profile_digest,
                       "policy": self.store._durability.account_switch_safety.policy_digest})

    def produce(self, *, signal, risk_evaluation, execution_risk_gate, quote):
        lifecycle = self.store.trade_lifecycle_service
        admission = lifecycle.runtime_admission_v2
        admission.require_execution_scope()
        self.store._durability.account_switch_safety._assert_identity()
        operation = self.store._durability.operation
        if (not self.store._durability.enabled or not isinstance(operation, dict)
                or not isinstance(risk_evaluation, dict) or not isinstance(execution_risk_gate, dict)
                or risk_evaluation.get("approved") is not True or execution_risk_gate.get("execution") != "APPROVED"
                or execution_risk_gate.get("account") != self.binding.risk_profile_id
                or signal.get("contracts") != 1 or signal.get("symbol") != self.binding.instrument_root):
            raise ValueError("native controlled admission is not authorized")
        now = utc_us(admission.clock())
        runtime = deepcopy(self.runtime_evidence())
        self.binding.assert_claims(runtime)
        if (runtime.get("connected") is not True or type(runtime.get("position_quantity")) is not int or runtime.get("position_quantity") != 0
                or runtime.get("active_orders") != [] or runtime.get("sim_runtime_revalidation") != "PASS"
                or runtime.get("sim_execution_authority") != "DISABLED"):
            raise ValueError("native runtime identity/inventory unavailable")
        runtime_us = utc_us(datetime.fromisoformat(runtime["observed_at"]))
        signal_us = utc_us(datetime.fromisoformat(signal["generated_at"]))
        quote_us = utc_us(quote["timestamp"])
        from backend.market_data.sim_operator_binding_v2 import _MAX_EVIDENCE_AGE
        max_runtime = int(_MAX_EVIDENCE_AGE.total_seconds() * 1_000_000)
        max_signal = int(admission.settings.maximum_signal_age_seconds * 1_000_000)
        max_quote = int(admission.settings.maximum_quote_age_seconds * 1_000_000)
        deadline = min(signal_us+max_signal, quote_us+max_quote, runtime_us+max_runtime)
        from backend.instruments.instrument_profile_engine import InstrumentProfileEngine
        point = InstrumentProfileEngine().get_profile(symbol=self.binding.instrument_root)["point_value"]
        plan = {k: signal[k] for k in ("symbol", "direction", "contracts", "entry_price", "stop_loss", "take_profit")}
        risk_version = self.risk_version()
        values = {**self.binding.claims(), "account": "Sim101", "provider": "Simulator", "instrument": self.binding.instrument,
            "runtime_generation": str(self.binding.runtime_generation), "admission_id": uuid4().hex,
            "signal_id": signal["submission_id"], "plan_id": digest(plan), "operation_id": operation["operation_id"],
            "command_id": signal["native_command_id"], "client_order_id": operation["operation_id"],
            "approval_id": uuid4().hex, "activation_id": signal["native_activation_id"],
            "risk_approval_id": digest(execution_risk_gate), "risk_version": risk_version,
            "quote_id": digest({**quote, "timestamp": quote["timestamp"].isoformat()}), "runtime_id": runtime["runtime_ref"],
            "policy_version": risk_version, "side": "BUY" if signal["direction"] in {"BUY", "LONG"} else "SELL",
            "quantity": "1", "entry_price": str(signal["entry_price"]), "stop_price": str(signal["stop_loss"]),
            "target_price": str(signal["take_profit"]), "point_value": str(point),
            "risk_ceiling": str(min(execution_risk_gate["risk"], abs(signal["entry_price"]-signal["stop_loss"])*point)),
            "issued_us": str(now), "expires_us": str(deadline),
            "risk_expires_us": str(deadline), "signal_us": str(signal_us), "quote_us": str(quote_us), "runtime_us": str(runtime_us),
            "max_signal_age_us": str(max_signal), "max_quote_age_us": str(max_quote), "max_runtime_age_us": str(max_runtime),
            "protection_timeout_us": str(self.protection_timeout_us), "recovery_timeout_us": str(self.recovery_timeout_us),
            **{gate+"_approval": "APPROVED" for gate in ("risk", "probability", "confluence", "news", "market", "rr", "stop")}}
        envelope = self.authority.issue(values, now_us=now, instrument=self.binding.instrument,
            runtime_generation=self.binding.runtime_generation, risk_version=risk_version)
        self.store.record_admission(envelope)
        return {"accepted": True, "status": "ADMITTED_NATIVE_SUBMIT_DISABLED", "admission_digest": envelope.digest,
                "backend_account_id": self.binding.backend_account_id, "execution_domain": "SIM_NATIVE",
                "prepared_order": None, "execution": None, "position": None}


@dataclass(frozen=True)
class NativeSimRuntimeV3:
    binding: SimNativeAccountV3
    lifecycle: object
    store: NativeSimFinancialCheckpointV3
    manager: object

    def integration(self, *, spool, activation_directory, phase_directory, receipt_directory, event_bus):
        """Explicit write/reconciliation facade; never mounted on a read endpoint."""
        from backend.services.sim_native_integration_v3 import NativeSimIntegrationV3
        return NativeSimIntegrationV3(runtime=self, spool=spool, activation_directory=activation_directory,
            phase_directory=phase_directory, receipt_directory=receipt_directory, event_bus=event_bus)


def build_native_sim_runtime(*, binding: SimNativeAccountV3, namespace_root, authority_key: bytes,
                             runtime_evidence, protection_timeout_us: int, recovery_timeout_us: int,
                             settings=None, api_settings=None, envelope=None):
    if type(binding) is not SimNativeAccountV3:
        raise ValueError("explicit SIM_NATIVE account authority required")
    # Imports reuse the existing canonical owners, not a parallel financial engine.
    from backend.services.runtime_context_v2 import (
        ArmsSettings, APISettings, AccountStateManagerV2, PortfolioManagerV2, PositionSizingEngineV2,
        RiskManagerV2, PositionManagerV2, TradeHistoryManagerV2, PerformanceAnalyticsV2,
        ProtectiveOrderRegistryV2, OCOManagerV2, TradeJournalV2, TradeLifecycleServiceV2, ExecutionRiskGateV1)
    from backend.instruments.instrument_profile_engine import InstrumentProfileEngine
    from backend.risk.trade_risk_validator_v2 import TradeRiskValidatorV2
    from backend.risk.multi_account_risk_engine_v2 import MultiAccountRiskEngineV2
    from backend.services.runtime_admission_v2 import bind_runtime_admission
    manager = binding.manager()
    profile = manager.get_active_account()
    policy = replace(settings or ArmsSettings(), account_balance=float(profile.account_size), risk_percent=profile.risk_percent)
    api = api_settings or APISettings()
    limits = [v for v in (profile.daily_loss_limit, policy.internal_daily_loss_limit) if v is not None]
    daily = min(limits) if limits else None
    instruments = InstrumentProfileEngine()
    resolver = lambda symbol: profile.get_contract_limit(instruments.get_profile(symbol=symbol)["contract_class"])
    maximum = min(profile.get_contract_limit("MINI"), profile.get_contract_limit("MICRO"))
    account = AccountStateManagerV2(starting_balance=profile.account_size, maximum_daily_loss=daily,
        maximum_total_drawdown=profile.max_drawdown, profit_target=profile.profit_target, account_stage=profile.account_stage)
    portfolio = PortfolioManagerV2(starting_balance=profile.account_size, account_state_manager_v2=account)
    journal = TradeJournalV2()
    broker = DisabledNativeSimConnectorV3(binding)
    manager_exec = NativeAdmissionManagerV3(execution_mode="PAPER", maximum_contracts=maximum, contract_limit_resolver=resolver)
    manager_exec.execution_mode = "SIM_NATIVE"  # This manager can never prepare an executable order.
    lifecycle = TradeLifecycleServiceV2(execution_manager=manager_exec,
        paper_execution_engine=DisabledPaperEngineV3(fill_market_orders_immediately=False, slippage_points=0.0),
        broker_connector_v2=broker, position_manager=PositionManagerV2(instrument_profile_engine=instruments,
            point_value=instruments.get_profile(symbol=binding.instrument_root)["point_value"]),
        instrument_profile_engine=instruments, trade_history_manager=TradeHistoryManagerV2(),
        performance_analytics=PerformanceAnalyticsV2(risk_free_rate=0.0, trading_days_per_year=252), risk_manager_v2=RiskManagerV2(
            position_sizing_engine=PositionSizingEngineV2(), maximum_daily_loss=daily,
            maximum_total_drawdown=profile.max_drawdown, maximum_contracts=maximum,
            maximum_open_positions=api.maximum_open_positions, contract_limit_resolver=resolver),
        execution_risk_gate_v1=ExecutionRiskGateV1(validator=TradeRiskValidatorV2(risk_engine=MultiAccountRiskEngineV2(account_manager=manager))),
        portfolio_manager_v2=portfolio, starting_balance=profile.account_size, trade_journal_v2=journal,
        protective_order_registry_v2=ProtectiveOrderRegistryV2(), oco_manager_v2=OCOManagerV2())
    for owner in (account, portfolio, journal, lifecycle):
        owner.sim_native_account_binding = binding
    bind_runtime_admission(lifecycle, settings=api, policy=policy)
    store = NativeSimFinancialCheckpointV3(trade_lifecycle_service=lifecycle, authority_key=authority_key,
        account_binding=binding, namespace_root=namespace_root, envelope=envelope)
    safety = NativeAccountSafetyV3(binding=binding, lifecycle=lifecycle, manager=manager, settings=policy)
    store._durability.account_switch_safety = safety
    lifecycle.native_admission_producer_v3 = NativeAdmissionProducerV3(store=store, binding=binding, key=authority_key,
        runtime_evidence=runtime_evidence, protection_timeout_us=protection_timeout_us, recovery_timeout_us=recovery_timeout_us)
    return NativeSimRuntimeV3(binding, lifecycle, store, manager)


def build_provisioned_native_sim_runtime(**configuration):
    """Explicit production composition; loads CurrentUser authority, never creates it.

    Test-only key injection remains on build_native_sim_runtime. This boundary
    deliberately accepts neither an alternate key nor an alternate secret root.
    """
    if "authority_key" in configuration or "authority_root" in configuration:
        raise ValueError("canonical CurrentUser authority required")
    from backend.services.sim_native_authority_v3 import load_authority
    return build_native_sim_runtime(authority_key=load_authority(), **configuration)

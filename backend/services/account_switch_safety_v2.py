"""Phase 0.10A containment: no cross-account transition is implemented here."""
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from math import isfinite
from threading import Lock

from backend.connectors.paper_broker_connector_v2 import PaperBrokerConnectorV2
from backend.services.durable_execution_state_v2 import (
    AccountAdmissionRejected, evidence_path, verify,
)


@dataclass(frozen=True)
class RuntimeAccountIdentityV2:
    # The existing PAPER identity is not a profile name or a multi-account registry.
    account_id: str
    profile_name: str


class AccountSwitchRejected(ValueError):
    pass


class AccountSwitchSafetyV2:
    def __init__(self, *, store, account_manager):
        self.store = store
        self.lifecycle = store.trade_lifecycle_service
        self.durability = store._durability
        self.identity = RuntimeAccountIdentityV2(
            account_id=self.lifecycle.broker_connector_v2.account_id,
            profile_name=account_manager.get_active_account_name().strip().upper(),
        )
        self._profile = deepcopy(asdict(account_manager.get_active_account()))
        self._managers = []
        self._switch_lock = Lock()
        self.register_manager(account_manager)
        gate_manager = self.lifecycle.execution_risk_gate_v1.validator.risk_engine.account_manager
        self.register_manager(gate_manager)
        self._rules = self._runtime_rules()
        self.durability.account_switch_safety = self

    def register_manager(self, manager):
        if all(manager is not existing for existing in self._managers):
            self._managers.append(manager)
        manager._runtime_switch_safety = self

    def _runtime_rules(self):
        lifecycle = self.lifecycle
        portfolio = lifecycle.portfolio_manager_v2
        account = portfolio.account_state_manager_v2
        risk = lifecycle.risk_manager_v2
        broker = lifecycle.broker_connector_v2
        return {
            "starting_balances": (
                lifecycle.starting_balance, portfolio.starting_balance,
                account.get_state()["starting_balance"], broker.starting_balance,
            ),
            "daily_limits": (account.maximum_daily_loss, risk.maximum_daily_loss),
            "drawdown_limits": (account.maximum_total_drawdown, risk.maximum_total_drawdown),
            "profit_target": account.profit_target,
            "account_stage": account.account_stage,
            "contracts": tuple(
                (lifecycle.execution_manager.get_contract_limit(symbol), risk.get_contract_limit(symbol))
                for symbol in ("NQ", "MNQ", "ES", "MES")
            ),
        }

    def _assert_identity(self):
        identity = self.identity
        coordinator = getattr(self, "coordinator", None)
        if coordinator is not None:
            coordinator.assert_published(self)
        if self.lifecycle is not self.store.trade_lifecycle_service:
            raise AccountSwitchRejected("runtime_identity_unproven")
        broker = self.lifecycle.broker_connector_v2
        if (not isinstance(broker, PaperBrokerConnectorV2)
                or broker.account_id != identity.account_id
                or not broker.is_connected):
            raise AccountSwitchRejected("runtime_identity_unproven")
        for manager in self._managers:
            if (manager.get_active_account_name().strip().upper() != identity.profile_name
                    or manager._load_active_account().strip().upper() != identity.profile_name
                    or asdict(manager.get_active_account()) != self._profile):
                raise AccountSwitchRejected("runtime_identity_mismatch")
        if self._runtime_rules() != self._rules:
            raise AccountSwitchRejected("runtime_rules_changed")
        # An initial split must not be blessed merely because it stayed unchanged.
        rules, profile = self._rules, self._profile
        if (any(value != profile["account_size"] for value in rules["starting_balances"])
                or any(value != profile["max_drawdown"] for value in rules["drawdown_limits"])
                or rules["daily_limits"][0] != rules["daily_limits"][1]):
            raise AccountSwitchRejected("runtime_profile_mismatch")
        daily_limit = rules["daily_limits"][0]
        if (profile["daily_loss_limit"] is not None
                and (daily_limit is None or daily_limit > profile["daily_loss_limit"])):
            raise AccountSwitchRejected("runtime_profile_mismatch")
        for pair, contract_class in zip(rules["contracts"], ("MINI", "MICRO", "MINI", "MICRO")):
            maximum = self._managers[0].get_active_account().get_contract_limit(contract_class)
            if pair[0] != pair[1] or not 0 < pair[0] <= maximum:
                raise AccountSwitchRejected("runtime_profile_mismatch")

    def context(self):
        with self.durability.lock:
            self._assert_identity()
            return {
                "account_id": self.identity.account_id,
                "profile_name": self.identity.profile_name,
                "cross_account_switch_enabled": False,
            }

    def validate_signal(self, *, signal, risk_context):
        """Reject stale callers before any durable mutation or order preparation."""
        try:
            self._assert_identity()
            context = risk_context if isinstance(risk_context, dict) else {}
            if self.store.account_identity is not None:
                required = {"account_id", "profile_name", "account_balance", "risk_percent"}
                if not required <= context.keys():
                    raise AccountSwitchRejected("signal_account_context_required")
            for source in (signal if isinstance(signal, dict) else {}, context):
                if ("account_id" in source and source["account_id"] != self.identity.account_id
                        or "profile_name" in source and source["profile_name"] != self.identity.profile_name):
                    raise AccountSwitchRejected("signal_account_mismatch")
            if ("risk_percent" in context
                    and context["risk_percent"] != self._profile["risk_percent"]):
                raise AccountSwitchRejected("signal_account_risk_mismatch")
            if ("account_balance" in context and context["account_balance"]
                    != self.lifecycle.portfolio_manager_v2.get_available_balance()):
                raise AccountSwitchRejected("signal_account_balance_mismatch")
        except (AttributeError, KeyError, TypeError, ValueError, OSError) as exc:
            raise AccountAdmissionRejected(str(exc) if isinstance(exc, AccountSwitchRejected)
                                           else "runtime_identity_unproven") from exc

    @staticmethod
    def _empty(rows, reason):
        if not isinstance(rows, list):
            raise AccountSwitchRejected("activity_state_unproven")
        if rows:
            raise AccountSwitchRejected(reason)

    def _assert_quiescent(self):
        durability = self.durability
        if durability.active_operations or durability.depth or durability.operation is not None:
            raise AccountSwitchRejected("durable_operation_pending")
        if durability.failed or durability.stopped:
            raise AccountSwitchRejected("reconciliation_or_restart_required")
        if durability.path is not None:
            path = durability.path
            evidence = evidence_path(path)
            if (path.with_suffix(path.suffix + ".tmp").exists()
                    or evidence.with_suffix(evidence.suffix + ".tmp").exists()):
                raise AccountSwitchRejected("reconciliation_pending")
            if not path.is_file():
                raise AccountSwitchRejected("durable_state_unproven")
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                generation = verify(saved)
                self.store.validate_account_identity(saved)
                if self.store.account_identity is not None and generation != durability.generation:
                    raise ValueError("Unexpected durable generation.")
            except (ValueError, OSError):
                raise AccountSwitchRejected("reconciliation_pending") from None
        lifecycle = self.lifecycle
        portfolio = lifecycle.portfolio_manager_v2
        broker = lifecycle.broker_connector_v2
        self._empty(lifecycle.get_active_positions(), "lifecycle_position_active")
        self._empty(portfolio.get_open_positions(), "portfolio_position_active")
        positions = broker.get_positions()
        if not isinstance(positions, list) or any(not isinstance(p, dict) for p in positions):
            raise AccountSwitchRejected("paper_state_unproven")
        self._empty([p for p in positions if p.get("status") != "CLOSED"], "paper_position_active")
        orders = broker.get_orders()
        if not isinstance(orders, list) or any(not isinstance(o, dict) for o in orders):
            raise AccountSwitchRejected("paper_state_unproven")
        self._empty([o for o in orders if o.get("status") not in broker.VALID_FINAL_ORDER_STATUSES],
                    "order_pending")
        self._empty(self.store.protective_order_registry.list_protections(status="ACTIVE"),
                    "protection_active")
        self._empty(self.store.oco_manager.list_groups(status="ACTIVE"), "oco_active")
        state = portfolio.account_state_manager_v2.get_state()
        for field in ("open_positions", "open_risk", "unrealized_pnl"):
            value = state[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise AccountSwitchRejected("exposure_state_unproven")
            if value != 0:
                raise AccountSwitchRejected("exposure_active")
        # Validate all participants, including closed history, without restoring or mutating.
        self.store.validate_state(state=self.store.capture_state())

    def switch(self, *, account_id, profile_name):
        coordinator = getattr(self, "coordinator", None)
        if coordinator is not None:
            self._assert_identity()
            return coordinator.switch(account_id=account_id, profile_name=profile_name)
        if not self._switch_lock.acquire(blocking=False):
            raise AccountSwitchRejected("account_switch_in_progress")
        acquired = False
        started = False
        try:
            acquired = self.durability.lock.acquire(blocking=False)
            if not acquired:
                raise AccountSwitchRejected("runtime_operation_in_progress")
            if self.durability.account_switch_in_progress:
                raise AccountSwitchRejected("account_switch_in_progress")
            self.durability.account_switch_in_progress = True
            started = True
            self.durability.account_switch_epoch += 1
            self._assert_identity()
            self._assert_quiescent()
            if (account_id != self.identity.account_id
                    or profile_name != self.identity.profile_name):
                raise AccountSwitchRejected("account_switch_requires_coordinated_transition")
            # No writes, account events, resets, checkpoints, or ACCOUNT_CHANGED.
            return {"status": "ACCOUNT_UNCHANGED", "changed": False,
                    "account_id": self.identity.account_id,
                    "profile_name": self.identity.profile_name}
        except AccountSwitchRejected:
            raise
        except (AttributeError, KeyError, TypeError, ValueError, OSError):
            raise AccountSwitchRejected("runtime_safety_unproven") from None
        finally:
            if started:
                self.durability.account_switch_in_progress = False
            if acquired:
                self.durability.lock.release()
            self._switch_lock.release()

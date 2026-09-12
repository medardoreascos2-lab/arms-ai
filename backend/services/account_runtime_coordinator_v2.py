"""Coordinated PAPER account publication; the selector is the durable commit record."""
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from threading import Lock, RLock
from uuid import uuid4

from backend.accounts.account_config_manager_v2 import AccountConfigManagerV2
from backend.accounts.account_registry_v1 import AccountRegistryV1
from backend.services.account_switch_safety_v2 import AccountSwitchSafetyV2, AccountSwitchRejected
from backend.services.durable_execution_state_v2 import atomic_write, evidence_path, verify
from backend.services.runtime_context_v2 import build_runtime_context


@dataclass(frozen=True)
class PublishedAccountRuntimeV2:
    runtime: object
    application: object
    generation: int


class AccountRuntimeCoordinatorV2(AccountSwitchSafetyV2):
    """One immutable publication holds the complete account-dependent service graph."""

    def __init__(self, *, config_path, namespace_root, registry=None, settings=None,
                 application_factory=None, legacy_state_path=None):
        self.config_path = Path(config_path).resolve()
        self.root = Path(namespace_root).resolve()
        self.registry = deepcopy(registry or AccountRegistryV1())
        self.settings = settings
        self.application_factory = application_factory or self._application
        self.legacy_state_path = Path(legacy_state_path) if legacy_state_path else None
        self.lock = RLock()
        self._switch_lock = Lock()
        self._published = None
        self._catalog = None
        self._lease = None
        self.switching = False
        self.failed = False
        self.requests = 0
        self.phase = "STOPPED"

    @property
    def published(self):
        if self.failed or self._published is None:
            raise AccountSwitchRejected("account_runtime_unavailable")
        return self._published

    @property
    def identity(self):
        return self.published.runtime.account_switch_safety_v2.identity

    @staticmethod
    def _application(runtime, manager, directory):
        from backend.api.app import create_app
        return create_app(runtime_context=runtime, account_config_manager_v2=manager,
                          risk_event_store_path_v2=directory / "risk-events.json",
                          start_backtesting_background_worker=False)

    def _step(self, phase):
        self.phase = phase

    def _acquire_lease(self):
        # A process-wide account selector must have only one writer, even when
        # two processes are trying to activate different account directories.
        path = self.config_path.with_suffix(".json.lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        lease = path.open("a+b")
        try:
            import os
            if os.name == "nt":
                import msvcrt
                if lease.seek(0, 2) == 0:
                    lease.write(b"0")
                    lease.flush()
                lease.seek(0)
                msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            lease.close()
            raise AccountSwitchRejected("account_catalog_writer_active") from None
        self._lease = lease

    def _read_catalog(self):
        if self.config_path.with_suffix(self.config_path.suffix + ".tmp").exists():
            raise AccountSwitchRejected("account_catalog_commit_ambiguous")
        value = json.loads(self.config_path.read_text(encoding="utf-8"))
        if set(value) == {"active_account"}:
            # Bootstrap only explicitly clean PAPER installations. Never adopt,
            # ignore, or guess the owner of an old global snapshot.
            if self.legacy_state_path is not None:
                path = self.legacy_state_path
                if any(p.exists() for p in (path, evidence_path(path),
                        path.with_suffix(path.suffix + ".tmp"),
                        evidence_path(path).with_suffix(".json.tmp"))):
                    raise AccountSwitchRejected("legacy_snapshot_requires_explicit_migration")
            accounts = {"PAPER-" + uuid4().hex.upper(): {"profile_name": name}
                        for name in self.registry.list_accounts()}
            active = next((key for key, row in accounts.items()
                           if row["profile_name"] == value["active_account"]), None)
            if active is None:
                raise AccountSwitchRejected("unknown_active_profile")
            value = {"version": 2, "active_account": value["active_account"],
                     "active_account_id": active, "runtime_generation": 1,
                     "namespace_root": str(self.root), "accounts": accounts}
        self._validate_catalog(value)
        return value

    def _validate_catalog(self, value):
        if (not isinstance(value, dict) or value.get("version") != 2
                or value.get("namespace_root") != str(self.root)
                or type(value.get("runtime_generation")) is not int
                or value["runtime_generation"] < 1):
            raise AccountSwitchRejected("invalid_account_catalog")
        accounts = value.get("accounts")
        if not isinstance(accounts, dict) or not accounts:
            raise AccountSwitchRejected("invalid_account_catalog")
        for account_id, row in accounts.items():
            # Canonical IDs are opaque uppercase keys; never a path or profile.
            if (not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,127}", account_id)
                    or not isinstance(row, dict) or set(row) != {"profile_name"}):
                raise AccountSwitchRejected("invalid_account_identity")
            name = row["profile_name"]
            if not isinstance(name, str) or name != name.strip().upper():
                raise AccountSwitchRejected("invalid_account_profile")
            self.registry.get_account(name)
        active = accounts.get(value.get("active_account_id"))
        if active is None or active["profile_name"] != value.get("active_account"):
            raise AccountSwitchRejected("account_selector_mismatch")

    def snapshot_path(self, account_id):
        if account_id not in self._catalog["accounts"]:
            raise AccountSwitchRejected("unknown_account_id")
        path = (self.root / account_id / "runtime-state.json").resolve()
        if path.parent.parent != self.root:
            raise AccountSwitchRejected("account_namespace_escape")
        return path

    def _build(self, account_id, generation):
        name = self._catalog["accounts"][account_id]["profile_name"]
        path = self.snapshot_path(account_id)
        manager = AccountConfigManagerV2.for_runtime(
            config_path=self.config_path, registry=self.registry, profile_name=name)
        runtime = build_runtime_context(
            settings=self.settings, account_manager=manager, account_id=account_id,
            runtime_generation=generation, account_namespace=path)
        durability = runtime.execution_state_store._durability
        durability.lock = self.lock
        try:
            self._step("RECOVER_TARGET")
            runtime.startup_coordinator.startup_from(file_path=path)
            application = self.application_factory(runtime, manager, path.parent)
            application.state.account_switch_safety_v2 = self
            application.state.runtime_state_path_v2 = path
            application.state.account_runtime_generation = generation
            safety = runtime.account_switch_safety_v2
            safety._assert_identity()
            runtime.execution_state_store.validate_state(
                state=runtime.execution_state_store.capture_state())
            return PublishedAccountRuntimeV2(runtime, application, generation)
        except BaseException:
            durability.retired = True
            durability.release()
            raise

    def assert_published(self, safety):
        bundle = self.published
        if bundle.runtime.account_switch_safety_v2 is not safety:
            raise AccountSwitchRejected("account_runtime_retired")
        if self._read_catalog() != self._catalog:
            raise AccountSwitchRejected("account_selector_mismatch")

    def start(self):
        with self.lock:
            if self._published is not None:
                return self.published
            self._acquire_lease()
            candidate = None
            self.switching = True
            try:
                self._catalog = self._read_catalog()
                candidate = self._build(self._catalog["active_account_id"],
                                        self._catalog["runtime_generation"])
                candidate.runtime.execution_state_store._durability.account_switch_in_progress = True
                # The account checkpoint exists and was validated before the
                # durable selector can announce it.
                atomic_write(self.config_path, self._catalog)
                self._published = candidate
                candidate.runtime.account_switch_safety_v2.coordinator = self
                self._step("READY")
                candidate.runtime.execution_state_store._durability.account_switch_in_progress = False
                return candidate
            except BaseException:
                self.failed = True
                if candidate is not None:
                    candidate.runtime.execution_state_store._durability.release()
                self.close(checkpoint=False)
                raise
            finally:
                self.switching = False

    def context(self):
        with self.lock:
            if self.switching:
                raise AccountSwitchRejected("account_switch_in_progress")
            self.published.runtime.account_switch_safety_v2._assert_identity()
            return {"account_id": self.identity.account_id, "profile_name": self.identity.profile_name,
                    "runtime_generation": self.published.generation,
                    "cross_account_switch_enabled": True,
                    "accounts": [{"account_id": key, **row}
                                 for key, row in self._catalog["accounts"].items()]}

    def switch(self, *, account_id, profile_name):
        if not self._switch_lock.acquire(blocking=False):
            raise AccountSwitchRejected("account_switch_in_progress")
        acquired = False
        source = candidate = None
        old_catalog = None
        committed = False
        try:
            acquired = self.lock.acquire(blocking=False)
            if not acquired:
                raise AccountSwitchRejected("runtime_operation_in_progress")
            source = self.published
            d = source.runtime.execution_state_store._durability
            if self.switching or self.requests:
                raise AccountSwitchRejected("runtime_operation_in_progress")
            self.switching = True
            d.account_switch_in_progress = True
            d.account_switch_epoch += 1
            self._step("FREEZE")
            safety = source.runtime.account_switch_safety_v2
            safety._assert_identity()
            self._step("VERIFY_SOURCE")
            safety._assert_quiescent()
            row = self._catalog["accounts"].get(account_id)
            if row is None or row["profile_name"] != profile_name:
                raise AccountSwitchRejected("account_identity_profile_mismatch")
            if account_id == self.identity.account_id:
                return {"status": "ACCOUNT_UNCHANGED", "changed": False,
                        "account_id": account_id, "profile_name": profile_name,
                        "runtime_generation": source.generation}
            old_catalog = deepcopy(self._catalog)
            self._step("CHECKPOINT_SOURCE")
            # The coordinator owns the barrier and has proved no operation is
            # in flight. Only this checkpoint may bypass new-work admission.
            d._checkpoint()
            verify(json.loads(d.path.read_text(encoding="utf-8")))
            self._step("BUILD_TARGET")
            candidate = self._build(account_id, source.generation + 1)
            self._step("VALIDATE_TARGET")
            candidate.runtime.account_switch_safety_v2._assert_quiescent()
            # Publication does not reopen the candidate. Direct callers and
            # event listeners share the same admission freeze until READY.
            candidate.runtime.execution_state_store._durability.account_switch_in_progress = True
            catalog = {**old_catalog, "active_account_id": account_id,
                       "active_account": profile_name, "runtime_generation": candidate.generation}
            self._step("BEFORE_PUBLISH")
            if self._read_catalog() != old_catalog:
                raise AccountSwitchRejected("account_selector_mismatch")
            atomic_write(self.config_path, catalog)
            committed = True
            # The sole publication assignment; no request can enter between
            # durable commit and publication because the barrier is still held.
            self._catalog = catalog
            self._published = candidate
            candidate.runtime.account_switch_safety_v2.coordinator = self
            d.retired = True
            d.release()
            self._step("AFTER_PUBLISH")
            result = {"status": "ACCOUNT_CHANGED", "changed": True,
                      "account_id": account_id, "profile_name": profile_name,
                      "runtime_generation": candidate.generation}
            candidate.application.state.dashboard_event_bus_v2.publish(
                event_type="ACCOUNT_CHANGED", payload=result)
            self._step("READY")
            return result
        except BaseException as exc:
            # A replaced selector is a committed transition even if the process
            # loses its response. An uncertain write must never resume A.
            if old_catalog is not None:
                try:
                    committed = committed or json.loads(
                        self.config_path.read_text(encoding="utf-8")) != old_catalog
                except (OSError, ValueError):
                    committed = True
            if committed:
                self.failed = True
                if source is not None:
                    source.runtime.execution_state_store._durability.retired = True
                if candidate is not None:
                    candidate.runtime.execution_state_store._durability.retired = True
            if candidate is not None and candidate is not self._published:
                candidate.runtime.execution_state_store._durability.release()
            if not isinstance(exc, Exception):
                raise
            if committed:
                raise AccountSwitchRejected("account_transition_failed_closed") from exc
            if isinstance(exc, AccountSwitchRejected):
                raise
            raise AccountSwitchRejected("account_transition_failed") from exc
        finally:
            if acquired:
                if self.failed or (source is not None and source.runtime.execution_state_store._durability.failed):
                    self.failed = True
                    if self._published is not None:
                        self._published.runtime.execution_state_store._durability.retired = True
                    self.phase = "FAILED"
                elif self._published is not None:
                    self.phase = "READY"
                if source is not None:
                    source.runtime.execution_state_store._durability.account_switch_in_progress = False
                if candidate is self._published and candidate is not None and not self.failed:
                    candidate.runtime.execution_state_store._durability.account_switch_in_progress = False
                self.switching = False
                self.lock.release()
            self._switch_lock.release()

    def close(self, *, checkpoint=True):
        with self.lock:
            try:
                if self._published is not None:
                    d = self._published.runtime.execution_state_store._durability
                    try:
                        if checkpoint and not self.failed and not d.failed and not d.retired:
                            d.checkpoint()
                    finally:
                        d.retired = True
                        d.release()
            finally:
                if self._lease is not None:
                    self._lease.close()
                    self._lease = None
                self._published = None
                self.phase = "STOPPED"

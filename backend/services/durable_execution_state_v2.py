"""Synchronous PAPER checkpoints with a durable in-flight fence.

A pending record is intentionally not replayed: an interrupted operation may
have changed only some participants. Recovery must require reconciliation.
"""
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
from threading import RLock


def durable_mutation(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        owner = getattr(self, "trade_lifecycle_service", self)
        durability = getattr(owner, "_durability", None)
        if durability is None:
            return method(self, *args, **kwargs)
        with durability.mutation():
            return method(self, *args, **kwargs)
    return call


def state_locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._durability.lock:
            return method(self, *args, **kwargs)
    return call


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def atomic_write(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical(state) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if os.name != "nt":
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def seal(state, generation, phase):
    state = deepcopy(state)
    state["durability"] = {"version": 1, "generation": generation, "phase": phase}
    state["checksum"] = hashlib.sha256(canonical(state)).hexdigest()
    return state


def verify(state):
    if not isinstance(state, dict):
        raise ValueError("Invalid persisted state.")
    if "durability" not in state and "checksum" not in state:
        if state.get("execution_records") is not None:
            raise ValueError("Missing durability metadata for execution records.")
        return 0  # Legacy snapshots are validated separately; never invent records.
    candidate = dict(state)
    checksum = candidate.pop("checksum", None)
    if checksum != hashlib.sha256(canonical(candidate)).hexdigest():
        raise ValueError("Durability checksum mismatch.")
    metadata = candidate.get("durability", {})
    if (metadata.get("version") != 1 or metadata.get("phase") != "COMMITTED"
            or type(metadata.get("generation")) is not int
            or metadata["generation"] < 1):
        raise ValueError("Incomplete or unsupported durable operation; reconciliation required.")
    return metadata["generation"]


class DurableExecutionStateV2:
    def __init__(self, store):
        self.store = store
        self.lock = RLock()
        self.path = None
        self.generation = 0
        self.depth = 0
        self.failed = False
        self._lease = None
        self.enabled = False
        self.stopped = False

    def fail_closed(self):
        self.failed = True
        portfolio = self.store._risk_portfolio()
        if portfolio is not None:
            account = portfolio.account_state_manager_v2
            with account._lock:
                account._state["trading_blocked"] = True
                reasons = account._state["blocking_reasons"]
                if "durability_consistency_unproven" not in reasons:
                    reasons.append("durability_consistency_unproven")

    def acquire(self, path):
        if self.failed:
            raise RuntimeError("Durability failed closed; restart and reconcile.")
        path = Path(path).resolve()
        if self._lease is not None:
            if self.path != path:
                raise RuntimeError("Cannot change the active durability path.")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        lease = path.with_suffix(path.suffix + ".lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                if lease.seek(0, os.SEEK_END) == 0:
                    lease.write(b"0")
                    lease.flush()
                lease.seek(0)
                msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            lease.close()
            raise RuntimeError("Durable state already has a runtime writer.")
        self._lease = lease
        self.path = path
        self.stopped = False

    def release(self):
        with self.lock:
            if self._lease is not None:
                self._lease.close()
                self._lease = None
            self.path = None
            self.enabled = False
            self.stopped = True

    def enable(self):
        with self.lock:
            if self.store.trade_lifecycle_service.broker_connector_v2.execution_mode != "PAPER":
                raise ValueError("Durable runtime recovery is authorized only for PAPER.")
            self.checkpoint()
            self.enabled = True

    def checkpoint(self):
        if self.failed:
            raise RuntimeError("Durability failed closed; checkpoint denied.")
        if self.depth:
            raise RuntimeError("Cannot checkpoint an incomplete operation.")
        try:
            state = self.store.validate_state(state=self.store.capture_state())
            self.generation += 1
            committed = seal(state, self.generation, "COMMITTED")
            atomic_write(self.path, committed)
            self.store._remember_checkpoint(self.path, committed, self.generation)
            return state
        except BaseException:
            self.fail_closed()
            raise

    @contextmanager
    def mutation(self):
        with self.lock:
            if self.failed or self.stopped:
                raise RuntimeError("Durability failed closed; execution denied.")
            if not self.enabled:
                yield
                return
            outer = self.depth == 0
            try:
                if outer:
                    baseline = self.store.validate_state(state=self.store.capture_state())
                    atomic_write(self.path, seal(baseline, self.generation + 1, "PENDING"))
                self.depth += 1
                try:
                    yield
                finally:
                    self.depth -= 1
                if outer:
                    self.checkpoint()
            except BaseException:
                self.fail_closed()
                raise

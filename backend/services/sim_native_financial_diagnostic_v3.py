"""Bounded failure evidence, separate from all financial authority and projections.

Stage scopes observe exceptions without replacing them. With no active native
financial service operation they are inert, including on the PAPER path.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import os

from backend.services import sim_native_authority_v3 as authority


SCHEMA = "SIM_NATIVE_FINANCIAL_DIAGNOSTIC_V3"
STAGES = frozenset("SERVICE_START AUTHORITY_LOAD CONFIG_VERIFY RUNTIME_BUILD CHECKPOINT_START CHECKPOINT_OPEN CHECKPOINT_VERIFY CHECKPOINT_RESTORE CHECKPOINT_COMMIT PHASE_DISCOVERY PHASE_READ PHASE_VERIFY PHASE_APPLY RECEIPT_WRITE PROJECTION_APPLY OUTBOX_DELIVERY SERVICE_PUBLISH".split())
_active = ContextVar("sim_native_financial_diagnostic", default=None)
_exception_types = (PermissionError, FileNotFoundError, FileExistsError, TimeoutError,
                    OSError, ValueError, TypeError, KeyError, RuntimeError)


def _exception_type(exc):
    # Never serialize arbitrary subclass names or exception messages.
    return next((kind.__name__ for kind in _exception_types if isinstance(exc, kind)), "Exception")


@contextmanager
def stage(name):
    if name not in STAGES:
        raise ValueError("unknown diagnostic stage")
    observer = _active.get()
    try:
        yield
    except BaseException as exc:
        if observer is not None and observer.failure is None:
            observer.failure = (name, _exception_type(exc))
        raise


def phase_generation(value):
    observer = _active.get()
    if observer is not None:
        observer.native_phase_generation = _generation(value)


def _generation(value):
    return value if type(value) is int and 0 <= value <= 2**63-1 else None


class SimNativeFinancialDiagnosticV3:
    def __init__(self):
        self.failure = None
        self.native_phase_generation = None
        self.latest = None
        self.write_status = "NOT_ATTEMPTED"

    @contextmanager
    def operation(self):
        if _active.get() is self:
            yield
            return
        self.failure = None
        self.native_phase_generation = None
        token = _active.set(self)
        try:
            yield
        finally:
            _active.reset(token)

    def record(self, exc, *, runtime_generation=None, configuration_generation=None,
               checkpoint=None, projection=None):
        name, kind = self.failure or ("SERVICE_START", _exception_type(exc))
        def present(path):
            try:
                return path.is_file() if path is not None else False
            except OSError:
                return None  # Unknown is not evidence of absence.
        self.latest = dict(schema=SCHEMA, observed_at=datetime.now(timezone.utc).isoformat(),
            stage=name, status="UNAVAILABLE", error_code=name + "_FAILED", exception_type=kind,
            runtime_generation=_generation(runtime_generation),
            configuration_generation=_generation(configuration_generation),
            native_phase_generation=self.native_phase_generation,
            checkpoint_present=present(checkpoint), projection_present=present(projection))
        self.write_status = "FAILED"
        try:
            path = authority.safe_path(authority.authority_root() / "diagnostics" / "financial-latest-failure.json", authority=True)
            temporary = authority.safe_path(path.with_suffix(".json.tmp"), authority=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive temporary creation: never overwrite another writer or a
            # stale diagnostic artifact. A successful startup writes nothing here.
            with temporary.open("xb") as stream:
                try:
                    stream.write(json.dumps(self.latest, sort_keys=True, separators=(",", ":")).encode("ascii"))
                    stream.flush()
                    os.fsync(stream.fileno())
                except BaseException:
                    stream.close()
                    temporary.unlink(missing_ok=True)
                    raise
            try:
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            self.write_status = "WRITTEN"
        except Exception:
            # Diagnostic storage cannot grant health or escape the existing
            # fail-closed service handler. Sanitized evidence remains in memory.
            pass

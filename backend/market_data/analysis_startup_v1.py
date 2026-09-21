"""Fresh in-memory health gate. Files and GET requests cannot arm activation."""
import os
from threading import RLock
from uuid import UUID

from backend.market_data.analysis_time_profile_v1 import require
from backend.market_data.fresh_native_adapter_v1 import FreshNativeAdapterV1, WindowsQpc, local_path
from tools.native_timing_witness_v1 import live_process_start


class AnalysisStartupV1:
    def __init__(self, *, run_id, installed_exporter, qpc_clock=None):
        require(str(UUID(run_id)) == run_id, 'RUN_UUID')
        self.run_id = run_id
        self.pid = os.getpid()
        self.process_start = live_process_start(self.pid)
        require(self.process_start is not None, 'PROCESS_IDENTITY_UNAVAILABLE')
        self.clock = qpc_clock or WindowsQpc()
        self.epoch, self.frequency, self.last_now = self.clock()
        self.installed_exporter = installed_exporter
        self.lock = RLock()
        self.phase = 'BACKEND_STARTING'
        self.reason = None
        self.adapter = None
        self.worker_heartbeat = 0
        self.worker_qpc = self.last_now
        self.observations = []
        self.frontend = None

    def _now(self):
        epoch, frequency, now = self.clock()
        require(epoch == self.epoch and frequency == self.frequency and now >= self.last_now, 'STARTUP_CLOCK')
        self.last_now = now
        return now

    def revoke(self, reason):
        with self.lock:
            self.reason = self.reason or reason
            self.phase = 'FAILED'
            if self.adapter:
                self.adapter.revoke(reason)

    def poll(self):
        with self.lock:
            if self.phase == 'FAILED':
                return
            try:
                self.worker_qpc = self._now()
                self.worker_heartbeat += 1
                if self.adapter:
                    self.adapter.poll()
                    if self.adapter.status in ('REVOKED', 'DISCONNECTED'):
                        self.revoke(self.adapter.reason or 'ADAPTER_FAILED')
            except Exception:
                self.revoke('STARTUP_WORKER_FAILED')

    def health(self):
        # Deliberately no poll here: reads cannot manufacture worker advancement.
        with self.lock:
            return dict(run_id=self.run_id, pid=self.pid, process_start=self.process_start,
                phase=self.phase, reason=self.reason, worker_heartbeat=self.worker_heartbeat,
                worker_qpc=self.worker_qpc,
                adapter_heartbeat=None if self.adapter is None else self.adapter.heartbeat,
                adapter_status=None if self.adapter is None else self.adapter.status,
                activation_allowance_started=self.adapter is not None and self.adapter.activation_start is not None,
                analysis_only=True, order_submit_reachable=False)

    def verify_backend(self, health, listener_pid):
        with self.lock:
            try:
                require(self.phase == 'BACKEND_STARTING', 'BACKEND_GATE_ORDER')
                self._identity(health, listener_pid)
                require(health['phase'] == self.phase and health['worker_heartbeat'] > 0, 'BACKEND_NOT_HEALTHY')
                self.phase = 'BACKEND_HEALTHY'
            except Exception:
                self.revoke('BACKEND_HEALTH_FAILED')
                raise

    def _identity(self, health, listener_pid):
        require(health['run_id'] == self.run_id and health['pid'] == listener_pid == self.pid
                and health['process_start'] == self.process_start == live_process_start(self.pid), 'STALE_BACKEND')

    def verify_frontend(self, *, expected_pid, expected_start, actual_pid, http_status, build_id, html):
        with self.lock:
            try:
                require(self.phase == 'BACKEND_HEALTHY', 'FRONTEND_GATE_ORDER')
                require(expected_pid == actual_pid and expected_start is not None
                        and live_process_start(expected_pid) == expected_start, 'STALE_FRONTEND')
                require(http_status == 200 and build_id and build_id in html
                        and 'ANALYSIS ONLY' in html and 'ADAPTER_STATUS' in html, 'DASHBOARD_ROUTE_NOT_HEALTHY')
                self.frontend = (expected_pid, expected_start)
                self.phase = 'DASHBOARD_HEALTHY'
            except Exception:
                self.revoke('FRONTEND_HEALTH_FAILED')
                raise

    def prepare(self, directory):
        with self.lock:
            try:
                require(self.phase == 'DASHBOARD_HEALTHY', 'ADAPTER_GATE_ORDER')
                folder = local_path(directory)
                folder.mkdir(exist_ok=False)  # Never accept a prior empty inbox either.
                self.adapter = FreshNativeAdapterV1(directory=folder, installed_exporter=self.installed_exporter,
                    qpc_clock=self.clock, health_gated=True)
                self.phase = 'VERIFYING_WAITING'
            except Exception:
                self.revoke('ADAPTER_STARTUP_FAILED')
                raise

    def observe_waiting(self, health, listener_pid):
        with self.lock:
            try:
                require(self.phase == 'VERIFYING_WAITING', 'WAITING_GATE_ORDER')
                self._identity(health, listener_pid)
                require(health['phase'] == self.phase and health['worker_heartbeat'] <= self.worker_heartbeat
                        and health['adapter_heartbeat'] <= self.adapter.heartbeat
                        and 0 <= self._now()-health['worker_qpc'] <= 2*self.frequency, 'STALE_WAITING_SNAPSHOT')
                require(health['adapter_status'] == 'WAITING' and not health['activation_allowance_started']
                        and self.adapter.session is None and not any(self.adapter.directory.iterdir()), 'NOT_FRESH_WAITING')
                now = self._now()
                if self.observations:
                    prior = self.observations[-1]
                    require(now > prior[0] and health['worker_heartbeat'] > prior[1]
                            and health['adapter_heartbeat'] > prior[2], 'HEARTBEAT_NOT_ADVANCING')
                self.observations.append((now, health['worker_heartbeat'], health['adapter_heartbeat']))
            except Exception:
                self.revoke('WAITING_HEALTH_FAILED')
                raise

    def finish_health(self, *, backend_pid, frontend_pid, dashboard_status, allow_activation=False):
        with self.lock:
            try:
                require(self.phase == 'VERIFYING_WAITING' and len(self.observations) >= 3, 'HEALTH_GATES_INCOMPLETE')
                self._identity(self.health(), backend_pid)
                require(self.frontend == (frontend_pid, live_process_start(frontend_pid)) and dashboard_status == 200,
                        'HEALTH_RECHECK_FAILED')
                require(self._now()-self.observations[-1][0] <= 5*self.frequency, 'STALE_WAITING')
                require(self.adapter.status == 'WAITING' and not any(self.adapter.directory.iterdir()), 'NOT_FRESH_WAITING')
                if allow_activation:
                    self.adapter.arm_activation()
                    self.phase = 'AWAITING_OPERATOR_ACTIVATION'
                else:
                    self.phase = 'OFFLINE_VALIDATED_UNARMED'
            except Exception:
                self.revoke('FINAL_HEALTH_FAILED')
                raise

    def snapshot(self):
        with self.lock:
            value = self.adapter.snapshot() if self.adapter else dict(analysis_status='BLOCKED', market_stream='NOT_LIVE')
            value.update(startup_run_id=self.run_id, startup_phase=self.phase,
                         paper_entry_authority='DISABLED', sim_execution_authority='DISABLED', live_authority=False,
                         order_submit_reachable=False)
            return value

    def close(self):
        self.revoke('STARTUP_SHUTDOWN')

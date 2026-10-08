"""Explicit Current-Market LOCAL PAPER launcher; import/help never starts it.

Analysis startup retains analysis polling. This entry point owns one separately
bound loopback PAPER API and attaches its coordinator only at the existing
preactivation lifecycle seam. It never enables PAPER automatically.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
from secrets import compare_digest
import socket
from threading import Thread
import time
import urllib.request

from backend.backtesting.controller_paper_enable_command_v1 import (
    ControllerPaperEnableCommandV1,
)
from backend.backtesting.certified_current_paper_authority_factory_v1 import (
    _unique,
    create_certified_current_paper_service_v1,
)
from backend.backtesting.native_current_paper_lifecycle_v1 import (
    NativeCurrentPaperLifecycleV1,
)
from backend.services import sim_native_authority_v3 as native_auth
from backend.services.sim_native_l1_authority_v1 import (
    private_directory_identity,
)
from backend.services.sim_native_authority_v3 import _restrict_directory


def _authenticated_paper_command(*, port, token, command,
                                 request_id=None, request_nonce=None):
    '''Call only the existing loopback authenticated PAPER control endpoint.'''
    if command not in ('enable', 'disable'):
        raise ValueError('CONTROLLER_PAPER_COMMAND_NOT_ALLOWED')
    headers = {'X-ARMS-ADMIN-TOKEN': token}
    if request_id is not None or request_nonce is not None:
        if type(request_id) is not str or type(request_nonce) is not str:
            raise ValueError('CONTROLLER_REQUEST_IDENTITY_REQUIRED')
        headers.update({'X-ARMS-REQUEST-ID': request_id,
                        'X-ARMS-REQUEST-NONCE': request_nonce})
    request = urllib.request.Request(
        f'http://127.0.0.1:{port}/api/v2/paper/{command}',
        data=b'', method='POST', headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=3) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
        if response.status != 200 or len(raw) > 4 * 1024 * 1024:
            raise RuntimeError('CURRENT_PAPER_CONTROL_FAILED')
    value = json.loads(raw.decode('utf-8'))
    if type(value) is not dict:
        raise RuntimeError('CURRENT_PAPER_CONTROL_RESPONSE_INVALID')
    return value


def _controller_paper_readiness(*, lifecycle, service, expected_session,
                                native_spec_path, reviewed_spec_sha256,
                                phase2_state_provider):
    '''Fresh, fail-closed readiness used only immediately before PAPER enable.'''
    statuses = {key: 'BLOCKED' for key in (
        'NATIVE_SPEC', 'NEWS', 'CATCHUP', 'LIVE_STREAM', 'L1', 'ANALYSIS',
        'SESSION_LINEAGE', 'PHASE2_STATE', 'MARKET_IDENTITY',
        'SAFETY_AUTHORITIES')}
    spec = None
    try:
        current_spec = Path(native_spec_path).read_bytes()
        if (type(reviewed_spec_sha256) is str
                and len(reviewed_spec_sha256) == 64
                and compare_digest(sha256(current_spec).hexdigest(),
                                   reviewed_spec_sha256)):
            statuses['NATIVE_SPEC'] = 'PASS'
            spec = json.loads(current_spec.decode('utf-8'),
                              object_pairs_hook=_unique)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        pass
    if type(spec) is dict:
        contract = spec.get('contract')
        if (spec.get('provider_enum') == 'Provider31'
                and type(contract) is dict
                and contract.get('provider') == 'Provider31'
                and contract.get('instrument') == 'NQ'
                and contract.get('contract') == 'NQ DEC26'
                and contract.get('trading_hours_template')
                == 'CME US Index Futures ETH'
                and contract.get('source_timezone') == 'UTC'
                and contract.get('bar_label') == 'CLOSE'
                and contract.get('fixture') is False
                and spec.get('order_authority') is False):
            statuses['MARKET_IDENTITY'] = 'PASS'
    try:
        phase2_state = phase2_state_provider()
        if (type(phase2_state) is dict
                and phase2_state.get('state') == 'RUNNING_DISABLED'
                and phase2_state.get('paper_execution_enabled') is False
                and phase2_state.get('live_execution_allowed') is False
                and phase2_state.get('external_order_authority') is False
                and phase2_state.get('broker_live_order_authority') is False
                and phase2_state.get('ninjatrader_control_authority') is False):
            statuses['PHASE2_STATE'] = 'RUNNING_DISABLED'
    except (OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    try:
        snapshot = lifecycle.check()
        runtime = lifecycle.analysis_runtime
        adapter = runtime.adapter
        coordinator = snapshot.get('coordinator') or {}
        bridge = coordinator.get('bridge') or {}
        if (runtime.phase == 'AWAITING_OPERATOR_ACTIVATION'
                and runtime.reason is None and adapter.reason is None):
            statuses['ANALYSIS'] = 'PASS'
        if (runtime.bootstrap_replacement_count == 1
                and runtime.bootstrap is adapter.bootstrap):
            statuses['CATCHUP'] = 'PASS_CERTIFIED'
        if (snapshot.get('worker_alive') is True
                and snapshot.get('status') == 'LIVE'
                and coordinator.get('status') == 'LIVE'
                and coordinator.get('source_adapter_status') == 'LIVE_TAIL'
                and bridge.get('status') == 'LIVE'):
            statuses['LIVE_STREAM'] = 'PASS'
        if (expected_session is not None and adapter.session == expected_session
                and bridge.get('source_session') == expected_session):
            statuses['SESSION_LINEAGE'] = 'PASS'
        if (snapshot.get('live_execution_allowed') is False
                and snapshot.get('broker_authority') is False
                and snapshot.get('ninjatrader_account_access') is False
                and snapshot.get('native_order_authority') is False
                and snapshot.get('order_submit_reachable') is False):
            statuses['SAFETY_AUTHORITIES'] = 'PASS'
    except (ValueError, RuntimeError, TypeError, AttributeError):
        pass

    authority = service.entry_authority
    if authority is not None:
        try:
            now = service.gate.clock()
            news = authority.news.inspect(symbol='NQ', timestamp=now)
            if news.get('status') == 'CERTIFIED_CLEAR' and news.get('blocked') is False:
                statuses['NEWS'] = 'PASS'
        except (ValueError, RuntimeError, TypeError, AttributeError, OSError):
            pass
        try:
            view, quote = authority.l1.inspect()
            bid = None if quote is None else quote.get('bid')
            ask = None if quote is None else quote.get('ask')
            if (view.get('status') == 'FRESH' and quote is not None
                    and view.get('provider') == 'Provider31'
                    and view.get('contract') == 'NQ DEC26'
                    and view.get('instrument') == 'NQ'
                    and quote.get('symbol') == 'NQ'
                    and type(bid) in (int, float) and not isinstance(bid, bool)
                    and type(ask) in (int, float) and not isinstance(ask, bool)
                    and isfinite(bid) and isfinite(ask) and 0 < bid <= ask
                    and type(view.get('quote_age_seconds')) in (int, float)
                    and 0 <= view['quote_age_seconds']
                    <= authority.settings.maximum_quote_age_seconds
                    and ask - bid <= authority.settings.maximum_spread_points):
                statuses['L1'] = 'PASS'
        except (ValueError, RuntimeError, TypeError, AttributeError, OSError):
            pass

    paper = service.get_snapshot()
    reasons = paper.get('readiness_reasons')
    if type(reasons) is not list:
        reasons = ['READINESS_INVALID']
    if paper.get('paper_execution_enabled') is not False:
        reasons = list(dict.fromkeys(reasons + ['PAPER_ALREADY_ENABLED']))
    if (paper.get('live_execution_allowed') is not False
            or paper.get('external_order_authority') is not False
            or paper.get('broker_live_order_authority') is not False
            or paper.get('ninjatrader_control_authority') is not False):
        statuses['SAFETY_AUTHORITIES'] = 'BLOCKED'
        reasons = list(dict.fromkeys(reasons + ['UNSAFE_AUTHORITY_PRESENT']))
    config_hash = paper.get('config_hash')
    policy = paper.get('effective_policy')
    safety_identity = ((config_hash, deepcopy(policy))
                       if type(config_hash) is str and type(policy) is dict
                       else None)
    return {
        'statuses': statuses,
        'readiness_blockers': list(reasons),
        '_safety_identity': safety_identity,
    }


class _PaperApiLifecycleV1:
    """Close worker/coordinator, then PAPER API, before analysis runtime."""

    def __init__(self, *, analysis_runtime, service, server, bound_socket, clock,
                 command_directory, command_run_id, paper_port, admin_token,
                 native_spec_path, reviewed_spec_sha256,
                 one_click_run_directory):
        self.lifecycle = NativeCurrentPaperLifecycleV1(
            analysis_runtime=analysis_runtime,
            service=service,
            wall_clock=clock,
            l1_reader=service.l1_reader,
        )
        self.server = server
        self.bound_socket = bound_socket
        self.thread = None
        self.closed = False
        expected_session = analysis_runtime.adapter.preactivation_session
        self.command_channel = ControllerPaperEnableCommandV1(
            run_id=command_run_id,
            directory=command_directory,
            clock=clock,
            readiness_provider=lambda: _controller_paper_readiness(
                lifecycle=self.lifecycle, service=service,
                expected_session=expected_session,
                native_spec_path=native_spec_path,
                reviewed_spec_sha256=reviewed_spec_sha256,
                phase2_state_provider=lambda: __import__(
                    'tools.arms_one_click_runtime_phase2_v1',
                    fromlist=['status']).status(one_click_run_directory)),
            enable_call=lambda **identity: _authenticated_paper_command(
                port=paper_port, token=admin_token, command='enable',
                request_id=identity.get('request_id'),
                request_nonce=identity.get('nonce')),
            disable_call=lambda **identity: _authenticated_paper_command(
                port=paper_port, token=admin_token, command='disable',
                request_id=identity.get('request_id'),
                request_nonce=identity.get('nonce')),
            fail_closed_call=service.shutdown,
            restrict_directory=_restrict_directory,
        )

    def start(self):
        self.lifecycle.start()
        self.thread = Thread(
            target=self.server.run,
            kwargs={"sockets": [self.bound_socket]},
            name="arms-current-paper-api",
            daemon=True,
        )
        self.thread.start()
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if self.server.started and self.thread.is_alive():
                self.command_channel.start()
                print('PAPER_ENABLE_COMMAND_CHANNEL='
                      + str(self.command_channel.directory), flush=True)
                return
            if not self.thread.is_alive():
                break
            time.sleep(0.01)
        raise RuntimeError("PAPER_API_START_FAILED")

    def check(self):
        self.lifecycle.check()
        self.command_channel.check()
        if self.thread is None or not self.thread.is_alive() or not self.server.started:
            raise RuntimeError("PAPER_API_LOST")

    def runtime_health(self):
        """Return fresh lifecycle evidence or fail the health request closed."""
        snapshot = self.lifecycle.check()
        coordinator = snapshot.get('coordinator')
        if type(coordinator) is not dict:
            raise RuntimeError('PAPER_RUNTIME_COORDINATOR_INVALID')
        return snapshot

    def close(self):
        if self.closed:
            return
        self.closed = True
        worker_error = None
        try:
            try:
                self.command_channel.close()
            finally:
                self.lifecycle.close()
        except BaseException as error:
            worker_error = error
        finally:
            self.server.should_exit = True
            if self.thread is not None:
                self.thread.join(timeout=10.0)
            api_alive = self.thread is not None and self.thread.is_alive()
            self.bound_socket.close()
        if worker_error is not None:
            raise worker_error
        if api_alive:
            raise RuntimeError("PAPER_API_STOP_TIMEOUT")


def _reserve_paper_port(port):
    bound = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            bound.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        bound.bind(("127.0.0.1", port))
        bound.listen(128)
        return bound
    except BaseException:
        bound.close()
        raise


def _prepare_current_paper_l1_directory(
    *, requested, one_click_run_directory,
    restrict_directory=_restrict_directory,
):
    """Create exactly the sealed L1 target once and bind its file identity."""
    from tools import arms_one_click_runtime_v1 as phase1

    _, manifest, _, _, _ = phase1._load_and_verify(
        one_click_run_directory, allow_runtime_targets=True)
    expected = native_auth.safe_path(
        Path(manifest['targets']['current_paper_l1_directory']),
        authority=True)
    requested = native_auth.safe_path(Path(requested), authority=True)
    if requested != expected:
        raise ValueError('CURRENT_PAPER_L1_BINDING_MISMATCH')
    if requested.exists():
        raise ValueError('FRESH_CURRENT_PAPER_L1_DIRECTORY_REQUIRED')

    parent, _ = private_directory_identity(requested.parent)
    if parent != requested.parent:
        raise ValueError('CURRENT_PAPER_L1_PARENT_IDENTITY_MISMATCH')
    requested.mkdir(parents=False, exist_ok=False)
    created = requested.stat()
    created_identity = (created.st_dev, created.st_ino)
    try:
        restrict_directory(requested)
        checked, checked_identity = private_directory_identity(requested)
    except BaseException:
        # Keep the failed, run-scoped directory as evidence. Never reuse it.
        raise
    if checked != requested or checked_identity != created_identity:
        raise ValueError('CURRENT_PAPER_L1_DIRECTORY_REPLACED')
    return checked, checked_identity


def run_current_paper(args):
    """Construct once, reserve loopback, and delegate analysis to its owner."""
    if (
        not args.start_current_paper
        or any(type(port) is not int or not 1024 <= port <= 65535 for port in
               (args.port, args.frontend_port, args.paper_port))
        or len({args.port, args.frontend_port, args.paper_port}) != 3
        or not 0 < args.startup_chart_catchup_timeout <= 900
    ):
        raise ValueError("EXPLICIT_CURRENT_PAPER_AND_DISTINCT_PORTS_REQUIRED")
    token = os.environ.get(args.admin_token_env)
    if not token or not token.strip():
        raise ValueError("EXPLICIT_ADMIN_TOKEN_REQUIRED")
    namespace = Path(args.paper_run_namespace)
    one_click_run_directory = Path(args.one_click_run_directory).resolve(
        strict=True)
    if one_click_run_directory.name != namespace.name:
        raise ValueError('ONE_CLICK_RUN_BINDING_REQUIRED')
    if namespace.exists():
        raise ValueError("FRESH_PAPER_RUN_NAMESPACE_REQUIRED")

    from backend.api.current_paper_app_v1 import create_current_paper_app_v1
    from backend.backtesting.paper_research_v1 import PaperResearchConfigV1
    from backend.config.api_settings import APISettings
    from tools.analysis_native_startup_v1 import run as run_analysis
    import uvicorn

    spec_bytes = Path(args.native_spec).read_bytes()
    if (
        type(args.native_spec_sha256) is not str
        or len(args.native_spec_sha256) != 64
        or any(c not in "0123456789abcdef" for c in args.native_spec_sha256)
        or not compare_digest(sha256(spec_bytes).hexdigest(), args.native_spec_sha256)
    ):
        raise ValueError("REVIEWED_NATIVE_SPEC_SHA256_REQUIRED")
    if os.environ.get('ARMS_WINDOWS_JOB_SUPERVISED_V1') != namespace.name:
        raise ValueError('WINDOWS_JOB_SUPERVISION_REQUIRED')
    # Paths are explicit fields of the hash-pinned reviewed specification.
    spec = json.loads(spec_bytes, object_pairs_hook=_unique)
    template_bytes = Path(spec["calendar_evidence_file"]).read_bytes()
    loaded_bytes = Path(spec["loaded_calendar_evidence_file"]).read_bytes()
    settings = APISettings()
    config = PaperResearchConfigV1.load(args.paper_config)
    clock = lambda: datetime.now(timezone.utc)
    l1_directory, l1_directory_identity = _prepare_current_paper_l1_directory(
        requested=args.current_paper_l1_directory,
        one_click_run_directory=one_click_run_directory)
    service = create_certified_current_paper_service_v1(
        spec_bytes=spec_bytes,
        reviewed_spec_sha256=args.native_spec_sha256,
        template_bytes=template_bytes,
        loaded_calendar_bytes=loaded_bytes,
        config=config,
        settings=settings,
        state_path=namespace / "paper.sqlite",
        clock=clock,
        news_root=args.current_paper_news_root,
        l1_directory=l1_directory,
        l1_directory_identity=l1_directory_identity,
    )

    bound = None
    owner = None
    try:
        bound = _reserve_paper_port(args.paper_port)

        def runtime_health_provider():
            if owner is None:
                raise RuntimeError('PAPER_RUNTIME_LIFECYCLE_NOT_ATTACHED')
            return owner.runtime_health()

        app = create_current_paper_app_v1(
            service=service,
            admin_token=token,
            dashboard_origin=f"http://127.0.0.1:{args.frontend_port}",
            runtime_health_provider=runtime_health_provider,
        )
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=args.paper_port,
            access_log=False, log_level="warning",
        ))
        namespace.mkdir(parents=True, exist_ok=False)
        args.validate_offline = False

        def lifecycle_factory(*, analysis_runtime, run_directory):
            nonlocal owner
            if owner is not None:
                raise RuntimeError("PAPER_LIFECYCLE_REENTRY")
            owner = _PaperApiLifecycleV1(
                analysis_runtime=analysis_runtime,
                service=service,
                server=server,
                bound_socket=bound,
                clock=clock,
                command_directory=namespace / 'controller-command-v1',
                command_run_id=namespace.name,
                paper_port=args.paper_port,
                admin_token=token,
                native_spec_path=args.native_spec,
                reviewed_spec_sha256=args.native_spec_sha256,
                one_click_run_directory=one_click_run_directory,
            )
            return owner

        return run_analysis(args, lifecycle_factory=lifecycle_factory)
    finally:
        try:
            if owner is not None:
                owner.close()
        finally:
            try:
                if bound is not None:
                    bound.close()
            finally:
                service.shutdown()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-current-paper", action="store_true", required=True)
    parser.add_argument("--installed-exporter", type=Path, required=True)
    parser.add_argument("--bootstrap-evidence", type=Path, required=True)
    parser.add_argument("--bootstrap-sha256", required=True)
    parser.add_argument("--startup-chart-catchup-source", type=Path, required=True)
    parser.add_argument("--startup-chart-catchup-timeout", type=float, default=300.0)
    parser.add_argument("--native-spec", type=Path, required=True)
    parser.add_argument("--native-spec-sha256", required=True)
    parser.add_argument("--paper-config", type=Path, required=True)
    parser.add_argument("--runtime-parent", type=Path, required=True)
    parser.add_argument("--paper-run-namespace", type=Path, required=True)
    parser.add_argument("--one-click-run-directory", type=Path, required=True)
    parser.add_argument("--current-paper-news-root", type=Path, required=True)
    parser.add_argument("--current-paper-l1-directory", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--frontend-port", type=int, required=True)
    parser.add_argument("--paper-port", type=int, required=True)
    parser.add_argument("--admin-token-env", required=True)
    args = parser.parse_args(argv)
    return run_current_paper(args)


if __name__ == "__main__":
    main()

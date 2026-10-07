"""Owned local backend/frontend processes; no native UI or account interfaces."""
import json
from hashlib import sha256
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from uuid import uuid4

from backend.market_data.analysis_time_profile_v1 import require
from backend.market_data.analysis_startup_v1 import AnalysisStartupV1
from backend.market_data.chart_catchup_bridge_v1 import ALLOWED_BASE_SOURCES
from backend.market_data.exporter_identity_v1 import verify_exporter_source
from backend.market_data.fresh_native_adapter_v1 import local_path
from tools.native_timing_witness_v1 import live_process_start

ROOT = Path(__file__).resolve().parents[1]
KNOWN_STARTUP_TERMINAL_ERROR_CODES = frozenset({
    'UNEXPECTED_DATA_GAP',
})


def _startup_error_code(error):
    """Return only reviewed terminal startup diagnostics."""
    value = str(error)
    return value if value in KNOWN_STARTUP_TERMINAL_ERROR_CODES else None


def _shutdown_fault_telemetry(health):
    """Copy pre-cleanup diagnostic evidence without polling the runtime."""
    return dict(failure_type=health['reason'] if health['phase'] == 'FAILED' else None,
        analysis_phase=health['phase'], adapter_status=health['adapter_status'],
        adapter_reason=health.get('adapter_reason'),
        profile_fault=health.get('profile_fault'),
        profile_fault_first_qpc=health.get('profile_fault_first_qpc'),
        profile_fault_last_qpc=health.get('profile_fault_last_qpc'),
        profile_last_receipt_qpc=health.get('profile_last_receipt_qpc'),
        profile_last_emission_qpc=health.get('profile_last_emission_qpc'),
        profile_heartbeat_budget_qpc=health.get('profile_heartbeat_budget_qpc'),
        profile_processing_budget_qpc=health.get('profile_processing_budget_qpc'))


def listener_pid(port):
    require(type(port) is int and 1024 <= port <= 65535, 'PORT')
    output = subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        f"@(Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty OwningProcess -Unique) | ConvertTo-Json -Compress"],
        creationflags=subprocess.CREATE_NO_WINDOW, timeout=5, text=True,
        stderr=subprocess.PIPE).strip()
    owners = json.loads(output) if output else []
    owners = owners if isinstance(owners, list) else [owners]
    require(len(owners) == 1, 'LISTENER_IDENTITY_UNAVAILABLE')
    return owners[0]


def free_port(port):
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(('127.0.0.1', port))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('HEALTH_REDIRECT_FORBIDDEN')


def get(url):
    # Only URLs assembled from fixed loopback origins and route/asset paths.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(urllib.request.Request(url, headers={'Cache-Control': 'no-cache'}), timeout=3) as response:
        data = response.read(4*1024*1024+1)
        require(len(data) <= 4*1024*1024, 'HEALTH_RESPONSE_LIMIT')
        return response.status, data.decode('utf-8')


def await_http(url, alive, seconds=30):
    end = time.monotonic()+seconds
    while time.monotonic() < end:
        require(alive(), 'OWNED_PROCESS_DIED')
        try:
            return get(url)
        except (OSError, ValueError):
            time.sleep(.25)
    raise ValueError('HEALTH_HTTP_TIMEOUT')


def frontend_copy(folder):
    """Copy source/config only. No .env, old build, old state, or old evidence."""
    source = ROOT/'frontend'
    folder.mkdir(exist_ok=False)
    for name in ('src', 'public', 'dashboard-v2'):
        shutil.copytree(source/name, folder/name)
    for name in ('package.json', 'package-lock.json', 'tsconfig.json', 'next.config.ts',
                 'postcss.config.mjs', 'eslint.config.mjs', 'next-env.d.ts'):
        if (source/name).exists():
            shutil.copyfile(source/name, folder/name)
    # Dependency junction is in the isolated build, never an input/evidence path.
    quote = lambda p: "'"+str(p).replace("'", "''")+"'"
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        'New-Item -ItemType Junction -Path '+quote(folder/'node_modules')+' -Target '+quote(source/'node_modules')+' | Out-Null'],
        creationflags=subprocess.CREATE_NO_WINDOW, check=True, timeout=10)


FRONTEND_OS_ENV = {
    'PATH': 'PATH',
    'PATHEXT': 'PATHEXT',
    'SYSTEMROOT': 'SystemRoot',
    'WINDIR': 'WINDIR',
    'COMSPEC': 'COMSPEC',
    'TEMP': 'TEMP',
    'TMP': 'TMP',
    'USERPROFILE': 'USERPROFILE',
    'APPDATA': 'APPDATA',
    'LOCALAPPDATA': 'LOCALAPPDATA',
}


def frontend_build_env(*, backend_url, paper_port=None):
    """Pass only required Windows settings and explicit public origins to Next."""
    env = {}
    for key, value in os.environ.items():
        canonical = FRONTEND_OS_ENV.get(key.upper())
        if canonical is not None:
            require(canonical not in env, 'FRONTEND_ENV_DUPLICATE_OS_KEY')
            env[canonical] = value
    env.update(NEXT_PUBLIC_API_URL=backend_url, NEXT_TELEMETRY_DISABLED='1', NODE_ENV='production')
    if paper_port is not None:
        require(type(paper_port) is int and 1024 <= paper_port <= 65535, 'PAPER_PORT')
        env['NEXT_PUBLIC_CURRENT_PAPER_API_URL'] = f'http://127.0.0.1:{paper_port}'
    return env


def perform_startup_chart_catchup(
    *,
    runtime,
    run_directory,
    base_path,
    base_sha256,
    source_path,
    timeout_seconds,
    guard,
    prepared_request=None,
):
    from tools.startup_chart_catchup_v1 import (
        await_capture,
        certify_capture,
        prepare_request,
    )

    require(
        runtime.phase
        == 'VERIFYING_WAITING'
        and runtime.adapter is not None
        and runtime.adapter.status
        == 'WAITING'
        and runtime.adapter.activation_start
        is None
        and runtime.adapter.session
        is None
        and len(
            runtime.observations
        )
        >= 3,
        'STARTUP_CATCHUP_GATE_ORDER',
    )

    quarantined_session = (
        runtime.adapter
        .validate_preactivation_buffer(
            'STARTUP_CATCHUP_GATE_ORDER',
        )
    )

    require(
        quarantined_session
        is not None
        and runtime.adapter.preactivation_session
        == quarantined_session,
        'STARTUP_LIVE_QUARANTINE_REQUIRED',
    )

    if prepared_request is None:
        request = prepare_request(
            run_directory,
            runtime.bootstrap,
            latest_closed=True,
        )

    else:
        require(
            type(prepared_request)
            is dict,
            'STARTUP_CATCHUP_PREPARED_REQUEST',
        )

        request = prepared_request

        output_directory = request.get(
            'output_directory'
        )

        live_output_directory = request.get(
            'live_output_directory'
        )

        require(
            type(output_directory)
            is str
            and bool(output_directory)
            and type(live_output_directory)
            is str
            and bool(live_output_directory),
            'STARTUP_CATCHUP_PREPARED_REQUEST',
        )

        expected_capture = (
            Path(run_directory)
            .resolve()
            / 'chart-catchup'
        )

        actual_capture = (
            Path(
                output_directory
            )
            .resolve()
        )

        expected_live_output = (
            Path(run_directory)
            .resolve()
            / 'inbox'
        )

        actual_live_output = (
            Path(
                live_output_directory
            )
            .resolve()
        )

        require(
            request.get('schema')
            == 'arms.startup-chart-catchup-request.v1'
            and request.get('indicator')
            == 'ArmsChartCatchupBridgeV1'
            and request.get('capture_enabled')
            is True
            and request.get(
                'expected_provider_enum'
            )
            == 'Provider31'
            and request.get(
                'through_close_utc'
            )
            == 'LATEST_CLOSED'
            and request.get(
                'through_selection'
            )
            == 'CHART_LATEST_CLOSED'
            and request.get(
                'absolute_time_authority'
            )
            == 'NONE'
            and request.get(
                'observation_only'
            )
            is True
            and request.get(
                'runtime_admission'
            )
            is False
            and request.get(
                'execution_authority'
            )
            is False
            and actual_capture
            == expected_capture
            and actual_capture.is_dir()
            and actual_live_output
            == expected_live_output
            and actual_live_output.is_dir(),
            'STARTUP_CATCHUP_PREPARED_REQUEST',
        )

    print(
        'STARTUP_CHART_CATCHUP_REQUIRED=TRUE',
        flush=True,
    )

    print(
        'CATCHUP_CAPTURE_ENABLED=True',
        flush=True,
    )

    print(
        'CATCHUP_OUTPUT_DIRECTORY='
        + request[
            'output_directory'
        ],
        flush=True,
    )

    print(
        'CATCHUP_LIVE_OUTPUT_DIRECTORY='
        + request[
            'live_output_directory'
        ],
        flush=True,
    )

    print(
        'CATCHUP_EXPECTED_PROVIDER_ENUM='
        + request[
            'expected_provider_enum'
        ],
        flush=True,
    )

    print(
        'CATCHUP_FROM_CLOSE_UTC='
        + request[
            'from_close_utc'
        ],
        flush=True,
    )

    print(
        'CATCHUP_THROUGH_CLOSE_UTC='
        + request[
            'through_close_utc'
        ],
        flush=True,
    )

    print(
        'STARTUP_CHART_CATCHUP_WAITING_FOR_SEAL=TRUE',
        flush=True,
    )

    await_capture(
        Path(
            request[
                'output_directory'
            ]
        ),
        timeout_seconds=
            timeout_seconds,
        guard=guard,
    )

    guard()

    output = (
        Path(run_directory)
        / 'certified-chart-catchup.bundle.json'
    )

    certified = certify_capture(
        base_path=base_path,
        base_sha256=
            base_sha256,
        source_path=
            source_path,
        capture_directory=
            Path(
                request[
                    'output_directory'
                ]
            ),
        request=request,
        output_path=output,
    )

    guard()

    runtime.install_waiting_bootstrap(
        certified[
            'bootstrap'
        ]
    )

    require(
        runtime.phase
        == 'VERIFYING_WAITING'
        and runtime.adapter.status
        == 'WAITING'
        and runtime.adapter.activation_start
        is None
        and runtime.observations
        == []
        and runtime.bootstrap
        is certified['bootstrap'],
        'STARTUP_CATCHUP_INSTALL_STATE',
    )

    return request, certified


def _close_optional_lifecycle(
    lifecycle,
):
    """Return a lifecycle-close error instead of interrupting analysis cleanup."""
    if lifecycle is None:
        return None

    try:
        lifecycle.close()
    except BaseException as error:
        return error

    return None


def _build_optional_lifecycle(
    lifecycle_factory,
    *,
    runtime,
    run_directory,
    catchup_source,
    validate_offline,
):
    """Build one separately owned lifecycle at the certified attach seam."""
    if lifecycle_factory is None:
        return None

    require(
        callable(lifecycle_factory),
        'OPTIONAL_LIFECYCLE_FACTORY',
    )

    require(
        catchup_source is not None
        and not validate_offline
        and runtime.phase
        == 'VERIFYING_WAITING'
        and runtime.adapter is not None
        and runtime.adapter.status
        == 'WAITING'
        and runtime.adapter.reason
        is None
        and runtime.adapter.activation_start
        is None
        and runtime.adapter.session
        is None
        and runtime.adapter.preactivation_session
        is not None
        and len(runtime.observations)
        >= 3
        and runtime.bootstrap
        is not None
        and runtime.adapter.bootstrap
        is runtime.bootstrap,
        'OPTIONAL_LIFECYCLE_ATTACH_GATE',
    )

    lifecycle = lifecycle_factory(
        analysis_runtime=runtime,
        run_directory=run_directory,
    )

    require(
        lifecycle is not None,
        'OPTIONAL_LIFECYCLE_FACTORY_RETURN',
    )

    for method_name in (
        'start',
        'check',
        'close',
    ):
        require(
            callable(
                getattr(
                    lifecycle,
                    method_name,
                    None,
                )
            ),
            'OPTIONAL_LIFECYCLE_CONTRACT',
        )

    return lifecycle


def run(args, lifecycle_factory=None):
    import uvicorn
    from backend.api.market_analysis_time_app_v1 import create_market_analysis_time_app_v1
    require(os.name == 'nt', 'WINDOWS_SAME_HOST_REQUIRED')
    source = local_path(args.installed_exporter)
    identity = verify_exporter_source(source.read_bytes())
    from tools.certify_analysis_bootstrap_v1 import bounded_read, load_bootstrap
    bootstrap = load_bootstrap(args.bootstrap_evidence, args.bootstrap_sha256) if getattr(args, 'bootstrap_evidence', None) else None

    catchup_source = None
    if getattr(args, 'startup_chart_catchup_source', None) is not None:
        from backend.market_data.chart_catchup_source_identity_v1 import (
            verify_chart_catchup_source,
        )

        catchup_source = local_path(args.startup_chart_catchup_source)
        catchup_raw = bounded_read(catchup_source)

        verify_chart_catchup_source(
            catchup_raw,
            mismatch_reason='STARTUP_CATCHUP_INSTALLED_SOURCE',
        )

        require(
            bootstrap is not None
            and bootstrap.source
            in ALLOWED_BASE_SOURCES,
            'STARTUP_CATCHUP_NATIVE_BASE_REQUIRED',
        )

    free_port(args.port); free_port(args.frontend_port)
    node = shutil.which('node')
    require(node is not None, 'NODE_REQUIRED')
    run_id = str(uuid4())
    parent = local_path(args.runtime_parent)
    parent.mkdir(parents=True, exist_ok=True)
    folder = parent/run_id
    folder.mkdir(exist_ok=False)
    runtime = AnalysisStartupV1(
        run_id=run_id,
        installed_exporter=source,
        bootstrap=bootstrap,
        allow_unbound_one_click_binding=catchup_source is not None,
    )
    backend_url = f'http://127.0.0.1:{args.port}'
    frontend_url = f'http://127.0.0.1:{args.frontend_port}'
    health_url = backend_url+'/api/v2/market-analysis/health'
    dashboard_url = frontend_url+'/market-analysis'
    claim = dict(run_id=run_id, pid=runtime.pid, process_start=runtime.process_start,
        mode='OFFLINE_VALIDATION' if args.validate_offline else 'ANALYSIS_ONLY', exporter_identity=identity,
        bootstrap_sha256=bootstrap.sha256 if bootstrap else None,
        startup_chart_catchup_required=catchup_source is not None,
        backend_url=backend_url, dashboard_url=dashboard_url, input_directory=str(folder/'inbox'))
    with (folder/'claim.json').open('x') as f:
        json.dump(claim, f, indent=2)
    print('RUNTIME_DIRECTORY='+str(folder), flush=True)
    app = create_market_analysis_time_app_v1(runtime=runtime, dashboard_origin=frontend_url)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port,
                                         access_log=False, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    frontend = None
    lifecycle = None
    samples = []
    result = dict(claim, status='FAILED', activation_allowance_started=False)
    try:
        thread.start()
        _, body = await_http(health_url, thread.is_alive)
        runtime.verify_backend(json.loads(body), listener_pid(args.port))
        print('BACKEND_HEALTH=PASS; ACTIVATION_ALLOWANCE=NOT_STARTED', flush=True)
        frontend_dir = folder/'frontend'
        frontend_copy(frontend_dir)
        env = frontend_build_env(
            backend_url=backend_url,
            paper_port=getattr(args, 'paper_port', None),
        )
        cli = str(ROOT/'frontend/node_modules/next/dist/bin/next')
        with (folder/'frontend-build.log').open('x') as build_log:
            subprocess.run([node, cli, 'build', '--webpack'], cwd=frontend_dir, env=env,
                stdout=build_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
                check=True, timeout=300)
        build_id = (frontend_dir/'.next/BUILD_ID').read_text().strip()
        with (folder/'frontend-runtime.log').open('x') as runtime_log:
            frontend = subprocess.Popen([node, cli, 'start', '--hostname', '127.0.0.1', '--port', str(args.frontend_port)],
                cwd=frontend_dir, env=env, stdout=runtime_log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
        frontend_start = live_process_start(frontend.pid)
        status, html = await_http(dashboard_url, lambda: frontend.poll() is None)
        runtime.verify_frontend(expected_pid=frontend.pid, expected_start=frontend_start,
            actual_pid=listener_pid(args.frontend_port), http_status=status, build_id=build_id, html=html)
        # Load the exact page's scripts: a 200 shell with missing assets is not healthy.
        scripts = re.findall(r'<script[^>]+src="([^" ]+)"', html)
        require(scripts and all(p.startswith('/_next/') and '..' not in p for p in scripts), 'DASHBOARD_ASSETS')
        javascript = ''.join(get(frontend_url+p)[1] for p in scripts)
        require(backend_url in javascript, 'DASHBOARD_API_ORIGIN_MISMATCH')
        print('DASHBOARD_ROUTE=HTTP_200; ACTIVATION_ALLOWANCE=NOT_STARTED', flush=True)
        runtime.prepare(folder/'inbox')

        for _ in range(3):
            time.sleep(1)
            backend_pid = listener_pid(args.port)
            _, body = get(health_url)
            health = json.loads(body)
            runtime.observe_waiting(health, backend_pid)
            samples.append(health)

        pre_catchup_samples = []
        catchup_public = None

        if catchup_source is not None:
            from tools.startup_chart_catchup_v1 import (
                prepare_request,
            )

            prepared_request = (
                prepare_request(
                    folder,
                    runtime.bootstrap,
                    latest_closed=True,
                )
            )

            print(
                'STARTUP_OPERATOR_SETUP_REQUIRED=TRUE',
                flush=True,
            )

            print(
                'STARTUP_LIVE_QUARANTINE_REQUIRED=TRUE',
                flush=True,
            )

            print(
                'STARTUP_CHART_CATCHUP_REQUIRED=TRUE',
                flush=True,
            )

            print(
                'NINJATRADER_ACTION=ADD_FRESH_ArmsReadOnlyMarketV1_AND_ArmsChartCatchupBridgeV1_IN_ONE_APPLY',
                flush=True,
            )

            print(
                'STARTUP_OPERATOR_APPLY_COUNT=1',
                flush=True,
            )

            print(
                'LIVE_OUTPUT_DIRECTORY='
                + str(
                    folder
                    / 'inbox'
                ),
                flush=True,
            )

            print(
                'CATCHUP_LIVE_OUTPUT_DIRECTORY='
                + prepared_request[
                    'live_output_directory'
                ],
                flush=True,
            )

            print(
                'CATCHUP_CAPTURE_ENABLED=True',
                flush=True,
            )

            print(
                'CATCHUP_OUTPUT_DIRECTORY='
                + prepared_request[
                    'output_directory'
                ],
                flush=True,
            )

            print(
                'CATCHUP_EXPECTED_PROVIDER_ENUM='
                + prepared_request[
                    'expected_provider_enum'
                ],
                flush=True,
            )

            print(
                'CATCHUP_FROM_CLOSE_UTC='
                + prepared_request[
                    'from_close_utc'
                ],
                flush=True,
            )

            print(
                'CATCHUP_THROUGH_CLOSE_UTC='
                + prepared_request[
                    'through_close_utc'
                ],
                flush=True,
            )

            live_deadline = (
                time.monotonic()
                + args.startup_chart_catchup_timeout
            )

            live_session = None

            while live_session is None:
                live_session = (
                    runtime.adapter
                    .validate_preactivation_buffer(
                        'STARTUP_LIVE_QUARANTINE_INVALID',
                    )
                )

                if live_session is not None:
                    break

                require(
                    time.monotonic()
                    < live_deadline,
                    'STARTUP_LIVE_QUARANTINE_TIMEOUT',
                )

                require(
                    thread.is_alive()
                    and frontend.poll()
                    is None,
                    'STARTUP_LIVE_QUARANTINE_PROCESS_LOST',
                )

                time.sleep(1)

                backend_pid = listener_pid(
                    args.port
                )

                _, body = get(
                    health_url
                )

                health = json.loads(
                    body
                )

                runtime.observe_waiting(
                    health,
                    backend_pid,
                )

                samples.append(
                    health
                )

            require(
                live_session is not None
                and runtime.adapter.preactivation_session
                == live_session
                and runtime.adapter.session
                is None
                and runtime.adapter.status
                == 'WAITING'
                and runtime.adapter.activation_start
                is None,
                'STARTUP_LIVE_QUARANTINE_REQUIRED',
            )

            print(
                'STARTUP_LIVE_QUARANTINE_READY=TRUE',
                flush=True,
            )

            print(
                'STARTUP_LIVE_QUARANTINE_SESSION='
                + live_session,
                flush=True,
            )

            pre_catchup_samples = list(
                samples
            )

            def catchup_guard():
                require(
                    thread.is_alive()
                    and frontend.poll()
                    is None,
                    'STARTUP_CATCHUP_PROCESS_LOST',
                )

                require(
                    listener_pid(args.port)
                    == runtime.pid
                    and listener_pid(
                        args.frontend_port
                    )
                    == frontend.pid,
                    'STARTUP_CATCHUP_LISTENER_CHANGED',
                )

                dashboard_status, _ = get(
                    dashboard_url
                )

                health = runtime.health()

                quarantined_session = (
                    runtime.adapter
                    .validate_preactivation_buffer(
                        'STARTUP_CATCHUP_WAITING_LOST',
                    )
                )

                require(
                    dashboard_status == 200
                    and health['phase']
                    == 'VERIFYING_WAITING'
                    and health['adapter_status']
                    == 'WAITING'
                    and not health[
                        'activation_allowance_started'
                    ]
                    and runtime.adapter.session
                    is None
                    and quarantined_session
                    is not None
                    and runtime.adapter.preactivation_session
                    == quarantined_session
                    and getattr(
                        runtime.adapter,
                        'preactivation_lineage_root',
                        quarantined_session,
                    )
                    == live_session,
                    'STARTUP_CATCHUP_WAITING_LOST',
                )

            request, catchup_result = (
                perform_startup_chart_catchup(
                    runtime=runtime,
                    run_directory=folder,
                    base_path=
                        args.bootstrap_evidence,
                    base_sha256=
                        args.bootstrap_sha256,
                    source_path=
                        catchup_source,
                    timeout_seconds=
                        args.startup_chart_catchup_timeout,
                    guard=catchup_guard,
                    prepared_request=prepared_request,
                )
            )

            require(
                request
                is prepared_request,
                'STARTUP_CATCHUP_REQUEST_REPLACED',
            )

            catchup_public = {
                key: value
                for key, value
                in catchup_result.items()
                if key != 'bootstrap'
            }

            with (
                folder
                / 'chart-catchup-result.json'
            ).open('x') as handle:
                json.dump(
                    catchup_public,
                    handle,
                    indent=2,
                )

            print(
                'STARTUP_CHART_CATCHUP_CERTIFIED='
                + json.dumps(
                    {
                        'sha256':
                            catchup_result[
                                'sha256'
                            ],
                        'bars':
                            catchup_result[
                                'bars'
                            ],
                        'cutoff':
                            catchup_result[
                                'cutoff'
                            ],
                        'source':
                            catchup_result[
                                'source'
                            ],
                    }
                ),
                flush=True,
            )

            samples = []

            for _ in range(3):
                time.sleep(1)

                backend_pid = listener_pid(
                    args.port
                )

                _, body = get(
                    health_url
                )

                health = json.loads(
                    body
                )

                runtime.observe_waiting(
                    health,
                    backend_pid,
                )

                samples.append(
                    health
                )

            print(
                'POST_CATCHUP_WAITING_HEALTH_SAMPLES=3',
                flush=True,
            )

        lifecycle = _build_optional_lifecycle(
            lifecycle_factory,
            runtime=runtime,
            run_directory=folder,
            catchup_source=catchup_source,
            validate_offline=args.validate_offline,
        )

        if lifecycle is not None:
            lifecycle.start()

        status, _ = get(dashboard_url)
        frontend_pid = listener_pid(args.frontend_port)
        backend_pid = listener_pid(args.port)
        runtime.finish_health(backend_pid=backend_pid, frontend_pid=frontend_pid,
                              dashboard_status=status, allow_activation=not args.validate_offline)
        result.update(status='PASS', health=runtime.health(), samples=samples,
            pre_catchup_samples=pre_catchup_samples, startup_chart_catchup=catchup_public,
            effective_bootstrap_sha256=runtime.bootstrap.sha256 if runtime.bootstrap else None,
            frontend_pid=frontend.pid,
            frontend_process_start=frontend_start, build_id=build_id, dashboard_http_status=status,
            activation_allowance_started=runtime.adapter.activation_start is not None,
            activation_start_qpc=runtime.adapter.activation_start, qpc_frequency=runtime.frequency,
            activation_allowance_seconds=900, input_empty=not any((folder/'inbox').iterdir()))
        with (folder/'health-result.json').open('x') as f:
            json.dump(result, f, indent=2)
        print(json.dumps(result), flush=True)
        if not args.validate_offline:
            while runtime.phase != 'FAILED':
                time.sleep(1)

                if lifecycle is not None:
                    lifecycle.check()

                require(thread.is_alive() and frontend.poll() is None, 'RUNTIME_PROCESS_LOST')
                require(listener_pid(args.port) == runtime.pid and listener_pid(args.frontend_port) == frontend.pid,
                        'RUNTIME_LISTENER_CHANGED')
                get(dashboard_url)
    except KeyboardInterrupt as error:
        result.update(
            status='STOPPED',
            shutdown_reason='OPERATOR_INTERRUPT',
            interruption_type=type(error).__name__,
            pre_shutdown_health=runtime.health(),
        )
        raise
    except BaseException as error:
        runtime.revoke('STARTUP_OR_HEALTH_FAILED')
        result.update(
            status='FAILED',
            error_type=type(error).__name__,
            error_code=_startup_error_code(error),
            health=runtime.health(),
        )
        raise
    finally:
        propagating_error = (
            sys.exc_info()[0]
            is not None
        )

        pre_cleanup_health = runtime.health()

        lifecycle_close_error = (
            _close_optional_lifecycle(
                lifecycle
            )
        )

        if lifecycle_close_error is not None:
            result.update(
                lifecycle_close_failed=True,
                lifecycle_close_error_type=
                    type(
                        lifecycle_close_error
                    ).__name__,
            )

        runtime.close()
        server.should_exit = True
        thread.join(timeout=10)

        if frontend is not None and frontend.poll() is None:
            frontend.terminate()
            frontend.wait(timeout=10)

        result.update(
            _shutdown_fault_telemetry(pre_cleanup_health),
            final_health=runtime.health(),
            owned_frontend_stopped=
                frontend is None
                or frontend.poll() is not None,
            owned_backend_stopped=
                not thread.is_alive(),
        )

        with (
            folder
            / 'shutdown-result.json'
        ).open('x') as f:
            json.dump(
                result,
                f,
                indent=2,
            )

        if (
            lifecycle_close_error
            is not None
            and not propagating_error
        ):
            raise lifecycle_close_error

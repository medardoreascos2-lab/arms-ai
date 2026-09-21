"""Owned local backend/frontend processes; no native UI or account interfaces."""
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from uuid import uuid4

from backend.market_data.analysis_time_profile_v1 import require
from backend.market_data.analysis_startup_v1 import AnalysisStartupV1
from backend.market_data.exporter_identity_v1 import verify_exporter_source
from backend.market_data.fresh_native_adapter_v1 import local_path
from tools.native_timing_witness_v1 import live_process_start

ROOT = Path(__file__).resolve().parents[1]


def listener_pid(port):
    require(type(port) is int and 1024 <= port <= 65535, 'PORT')
    output = subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        f"@(Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty OwningProcess -Unique) | ConvertTo-Json -Compress"],
        creationflags=subprocess.CREATE_NO_WINDOW, timeout=5, text=True).strip()
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


def run(args):
    import uvicorn
    from backend.api.market_analysis_time_app_v1 import create_market_analysis_time_app_v1
    require(os.name == 'nt', 'WINDOWS_SAME_HOST_REQUIRED')
    source = local_path(args.installed_exporter)
    identity = verify_exporter_source(source.read_bytes())
    free_port(args.port); free_port(args.frontend_port)
    node = shutil.which('node')
    require(node is not None, 'NODE_REQUIRED')
    run_id = str(uuid4())
    parent = local_path(args.runtime_parent)
    parent.mkdir(parents=True, exist_ok=True)
    folder = parent/run_id
    folder.mkdir(exist_ok=False)
    runtime = AnalysisStartupV1(run_id=run_id, installed_exporter=source)
    backend_url = f'http://127.0.0.1:{args.port}'
    frontend_url = f'http://127.0.0.1:{args.frontend_port}'
    health_url = backend_url+'/api/v2/market-analysis/health'
    dashboard_url = frontend_url+'/market-analysis'
    claim = dict(run_id=run_id, pid=runtime.pid, process_start=runtime.process_start,
        mode='OFFLINE_VALIDATION' if args.validate_offline else 'ANALYSIS_ONLY', exporter_identity=identity,
        backend_url=backend_url, dashboard_url=dashboard_url, input_directory=str(folder/'inbox'))
    with (folder/'claim.json').open('x') as f:
        json.dump(claim, f, indent=2)
    print('RUNTIME_DIRECTORY='+str(folder), flush=True)
    app = create_market_analysis_time_app_v1(runtime=runtime, dashboard_origin=frontend_url)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port,
                                         access_log=False, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    frontend = None
    samples = []
    result = dict(claim, status='FAILED', activation_allowance_started=False)
    try:
        thread.start()
        _, body = await_http(health_url, thread.is_alive)
        runtime.verify_backend(json.loads(body), listener_pid(args.port))
        print('BACKEND_HEALTH=PASS; ACTIVATION_ALLOWANCE=NOT_STARTED', flush=True)
        frontend_dir = folder/'frontend'
        frontend_copy(frontend_dir)
        env = dict(os.environ, NEXT_PUBLIC_API_URL=backend_url, NEXT_TELEMETRY_DISABLED='1', NODE_ENV='production')
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
        status, _ = get(dashboard_url)
        frontend_pid = listener_pid(args.frontend_port)
        backend_pid = listener_pid(args.port)
        runtime.finish_health(backend_pid=backend_pid, frontend_pid=frontend_pid,
                              dashboard_status=status, allow_activation=not args.validate_offline)
        result.update(status='PASS', health=runtime.health(), samples=samples, frontend_pid=frontend.pid,
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
                require(thread.is_alive() and frontend.poll() is None, 'RUNTIME_PROCESS_LOST')
                require(listener_pid(args.port) == runtime.pid and listener_pid(args.frontend_port) == frontend.pid,
                        'RUNTIME_LISTENER_CHANGED')
                get(dashboard_url)
    except BaseException as error:
        runtime.revoke('STARTUP_OR_HEALTH_FAILED')
        result.update(status='FAILED', error_type=type(error).__name__, health=runtime.health())
        raise
    finally:
        runtime.close()
        server.should_exit = True
        thread.join(timeout=10)
        if frontend is not None and frontend.poll() is None:
            frontend.terminate()
            frontend.wait(timeout=10)
        result.update(final_health=runtime.health(), owned_frontend_stopped=frontend is None or frontend.poll() is not None,
                      owned_backend_stopped=not thread.is_alive())
        with (folder/'shutdown-result.json').open('x') as f:
            json.dump(result, f, indent=2)

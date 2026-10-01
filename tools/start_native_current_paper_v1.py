"""Explicit Current-Market LOCAL PAPER launcher; import/help never starts it.

Analysis startup retains analysis polling. This entry point owns one separately
bound loopback PAPER API and attaches its coordinator only at the existing
preactivation lifecycle seam. It never enables PAPER automatically.
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from secrets import compare_digest
import socket
from threading import Thread
import time

from backend.backtesting.certified_current_paper_authority_factory_v1 import (
    _unique,
    create_certified_current_paper_service_v1,
)
from backend.backtesting.native_current_paper_lifecycle_v1 import (
    NativeCurrentPaperLifecycleV1,
)


class _PaperApiLifecycleV1:
    """Close worker/coordinator, then PAPER API, before analysis runtime."""

    def __init__(self, *, analysis_runtime, service, server, bound_socket, clock):
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
                return
            if not self.thread.is_alive():
                break
            time.sleep(0.01)
        raise RuntimeError("PAPER_API_START_FAILED")

    def check(self):
        self.lifecycle.check()
        if self.thread is None or not self.thread.is_alive() or not self.server.started:
            raise RuntimeError("PAPER_API_LOST")

    def close(self):
        if self.closed:
            return
        self.closed = True
        worker_error = None
        try:
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
    # Paths are explicit fields of the hash-pinned reviewed specification.
    spec = json.loads(spec_bytes, object_pairs_hook=_unique)
    template_bytes = Path(spec["calendar_evidence_file"]).read_bytes()
    loaded_bytes = Path(spec["loaded_calendar_evidence_file"]).read_bytes()
    settings = APISettings()
    config = PaperResearchConfigV1.load(args.paper_config)
    clock = lambda: datetime.now(timezone.utc)
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
        l1_directory=args.current_paper_l1_directory,
    )

    bound = None
    owner = None
    try:
        bound = _reserve_paper_port(args.paper_port)
        app = create_current_paper_app_v1(
            service=service,
            admin_token=token,
            dashboard_origin=f"http://127.0.0.1:{args.frontend_port}",
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

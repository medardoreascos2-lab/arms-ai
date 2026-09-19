"""Explicit PAPER RC entrypoint. No general broker/order routes are mounted."""
from contextlib import asynccontextmanager
from hashlib import sha256

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.api.admin_authorization_dependency_v2 import require_admin_authorization_v2
from backend.backtesting.paper_runtime_v1 import OperatingModeV1, PaperRuntimeV1
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


def create_paper_rc_app_v1(*, mode, configuration_id, runtime=None, admin_token=None,
                           dashboard_origin="http://localhost:3000"):
    mode = OperatingModeV1(mode)
    if not isinstance(configuration_id, str) or not configuration_id.strip():
        raise ValueError("explicit configuration identity required")
    if runtime is not None and (type(runtime) is not PaperRuntimeV1 or mode is not OperatingModeV1.PAPER_RESEARCH):
        raise ValueError("only isolated PAPER_RESEARCH runtime is supported")

    @asynccontextmanager
    async def lifespan(app):
        yield
        if runtime is not None:
            runtime.shutdown()

    app = FastAPI(title="ARMS AI certified replay PAPER RC", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[dashboard_origin],
                       allow_methods=["GET", "POST"], allow_headers=["X-ARMS-ADMIN-TOKEN", "Content-Type"])
    if admin_token:
        app.state.admin_authorization_v2 = AdminAuthorizationV2(token=admin_token)

    def snapshot():
        if runtime is not None:
            return runtime.get_snapshot()
        return {"mode": mode.value, "config_hash": sha256(configuration_id.encode()).hexdigest(),
                "paper_ready": False, "dashboard_status": "BLOCKED",
                "readiness_reasons": ["PAPER_RUNTIME_NOT_CONFIGURED"], "live_execution_allowed": False}

    @app.get("/health")
    def health():
        return {"status": "PROCESS_HEALTHY", "mode": mode.value, "live_execution_allowed": False}

    @app.get("/api/v2/paper/readiness")
    def readiness():
        value = snapshot()
        return {k: value[k] for k in ("mode", "config_hash", "paper_ready", "readiness_reasons")}

    @app.get("/api/v2/backtesting/dashboard")
    def dashboard():
        return {"paper_research": snapshot()}

    @app.post("/api/v2/paper/{command}", dependencies=[Depends(require_admin_authorization_v2)])
    def command(command: str):
        if runtime is None:
            raise HTTPException(409, "PAPER_RUNTIME_NOT_CONFIGURED")
        try:
            if command == "step":
                return runtime.step()
            if command == "shutdown":
                runtime.shutdown()
                return runtime.get_snapshot()
            return runtime.control(command)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from None

    return app


def load_certified_replay(*, manifest_path, contract):
    """Read-only verified Sprint05 stream; no implicit dataset or fake fallback."""
    import json
    from pathlib import Path
    from backend.backtesting.historical_eligibility_v31 import HistoricalEligibilityV31
    declaration = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    matches = [s for s in declaration["segments"] if s["contract"] == contract]
    if len(matches) != 1:
        raise ValueError("one explicitly certified independent contract required")
    segment = matches[0]
    for path_key, digest_key in (("stream", "stream_sha256"), ("source_file", "source_sha256")):
        if sha256(Path(segment[path_key]).read_bytes()).hexdigest() != segment[digest_key]:
            raise ValueError("certified input hash mismatch")
    policy = HistoricalEligibilityV31(declaration["calendar"])
    rows = []
    for line in Path(segment["stream"]).read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        row = policy.observation(value["raw_row"], contract=contract, source_file=segment["source_file"],
                                 source_sha256=segment["source_sha256"], source_row=value["source_row"])
        rows.append(row)
    policy.validate_segment(rows, contract=contract)
    return policy, tuple(rows)


def main():
    import argparse
    import os
    import uvicorn
    from backend.backtesting.paper_research_v1 import PaperResearchConfigV1
    from backend.config.api_settings import APISettings
    parser = argparse.ArgumentParser(description="Explicit certified-replay PAPER RC only")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--initialization-policy", required=True, choices=["NEW_ISOLATED_PAPER_ACCOUNT"])
    args = parser.parse_args()
    token = os.environ.get("ARMS_ADMIN_TOKEN")
    if not token:
        parser.error("ARMS_ADMIN_TOKEN required; never put credentials in command arguments")
    policy, rows = load_certified_replay(manifest_path=args.manifest, contract=args.contract)
    config = PaperResearchConfigV1.load(args.config)
    runtime = PaperRuntimeV1(mode="PAPER_RESEARCH", config=config, settings=APISettings(),
        policy=policy, observations=rows, contract=args.contract, state_path=args.state,
        initialization_policy=args.initialization_policy)
    app = create_paper_rc_app_v1(mode="PAPER_RESEARCH", configuration_id=config.version,
                                runtime=runtime, admin_token=token)
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()

"""ASGI publication boundary: each request uses one complete account application."""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.responses import JSONResponse


class AccountRuntimeApplicationV2(FastAPI):
    def __init__(self, coordinator):
        self.coordinator = coordinator

        @asynccontextmanager
        async def lifespan(app):
            coordinator.start()
            try:
                yield
            finally:
                coordinator.close()

        super().__init__(lifespan=lifespan)
        self._bootstrap_state.account_runtime_coordinator_v2 = coordinator

    @property
    def state(self):
        bundle = self.coordinator._published
        return bundle.application.state if bundle is not None else self._bootstrap_state

    @state.setter
    def state(self, value):
        self._bootstrap_state = value

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await super().__call__(scope, receive, send)
        coordinator = self.coordinator
        if coordinator.switching or coordinator.failed or coordinator._published is None:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1013})
            else:
                await JSONResponse(status_code=409, content={
                    "accepted": False, "changed": False,
                    "reason": "account_runtime_unavailable",
                })(scope, receive, send)
            return
        # Do not wait behind a switch and accidentally admit a stale request.
        if not coordinator.lock.acquire(blocking=False):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1013})
            else:
                await JSONResponse(status_code=409, content={
                    "accepted": False, "changed": False,
                    "reason": "runtime_operation_in_progress",
                })(scope, receive, send)
            return
        counted = False
        try:
            bundle = coordinator.published
            is_switch = scope.get("method") == "POST" and scope.get("path") in {
                "/api/v2/dashboard/account-manager/switch", "/api/v2/dashboard/account/switch"}
            if scope["type"] == "http" and not is_switch:
                coordinator.requests += 1
                counted = True
        finally:
            coordinator.lock.release()

        if scope["type"] == "websocket":
            # An old socket cannot continue projecting A after publication of B.
            async def watch():
                while coordinator._published is bundle and not coordinator.failed:
                    await asyncio.sleep(.025)
                await send({"type": "websocket.close", "code": 1012})
            async def account_send(message):
                if coordinator._published is not bundle or coordinator.failed:
                    raise RuntimeError("Retired account socket")
                await send(message)
            worker = asyncio.create_task(bundle.application(scope, receive, account_send))
            watcher = asyncio.create_task(watch())
            try:
                await asyncio.wait((worker, watcher), return_when=asyncio.FIRST_COMPLETED)
            finally:
                worker.cancel()
                watcher.cancel()
                await asyncio.gather(worker, watcher, return_exceptions=True)
            return
        try:
            await bundle.application(scope, receive, send)
        finally:
            if counted:
                with coordinator.lock:
                    coordinator.requests -= 1

"""Loopback-only Product notification inbox API for local test/development."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from typing import Callable, Literal

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from backend.product.customer_session import CustomerSessionProvider
from backend.product.notification_store import NotificationScope, ProductNotificationStore


def _unavailable(status: str) -> JSONResponse:
    return JSONResponse({
        "status": status,
        "notifications": [],
        "external_delivery_authorized": False,
        "financial_authority": False,
        "execution_authorized": False,
        "portfolio_mutation_authorized": False,
    })


def create_local_test_product_notification_router(
    *,
    session_provider: CustomerSessionProvider,
    notification_store: ProductNotificationStore,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    if session_provider is None or notification_store is None:
        raise TypeError("session provider and notification store are required")
    now = clock or (lambda: datetime.now(timezone.utc))
    router = APIRouter(
        prefix="/product/notifications",
        tags=["product-notifications-local-test"],
    )

    def scope_for(request: Request, session_id: str | None) -> NotificationScope | None:
        try:
            peer = ip_address(request.client.host if request.client else "")
        except ValueError:
            return None
        if not peer.is_loopback or not session_id:
            return None
        evaluated_at = now()
        session = session_provider.validate_session(session_id, evaluated_at)
        if session is None:
            return None
        return NotificationScope(
            tenant_id=session.tenant_id,
            user_id=session.user_id,
        )

    @router.get("")
    def inbox(
        request: Request,
        session_id: str | None = Header(
            default=None, alias="X-ARMS-Local-Test-Session",
        ),
    ):
        scope = scope_for(request, session_id)
        if scope is None:
            return _unavailable("SESSION_INVALID")
        try:
            items = notification_store.list(scope)
        except Exception:
            return _unavailable("NOTIFICATION_DATA_UNAVAILABLE")
        return {
            "status": "READY",
            "notifications": [
                item.model_dump(mode="json") for item in items
            ],
            "source_status": "LOCAL_TEST_ONLY",
            "external_delivery_authorized": False,
            "financial_authority": False,
            "execution_authorized": False,
            "portfolio_mutation_authorized": False,
        }

    def transition(
        request: Request, session_id: str | None, notification_id: str,
        action: Literal["read", "acknowledge", "snooze", "dismiss"],
    ):
        scope = scope_for(request, session_id)
        if scope is None:
            return _unavailable("SESSION_INVALID")
        evaluated_at = now()
        try:
            if action == "read":
                item = notification_store.mark_read(
                    scope, notification_id, evaluated_at,
                )
            elif action == "acknowledge":
                item = notification_store.acknowledge(
                    scope, notification_id, evaluated_at,
                )
            elif action == "snooze":
                item = notification_store.snooze(
                    scope, notification_id,
                    evaluated_at + timedelta(hours=1), evaluated_at,
                )
            else:
                item = notification_store.dismiss(
                    scope, notification_id, evaluated_at,
                )
        except PermissionError:
            return _unavailable("PERMISSION_BLOCKED")
        except Exception:
            return _unavailable("NOTIFICATION_DATA_UNAVAILABLE")
        return {
            "status": "READY",
            "notification": item.model_dump(mode="json"),
            "source_status": "LOCAL_TEST_ONLY",
            "external_delivery_authorized": False,
            "financial_authority": False,
            "execution_authorized": False,
            "portfolio_mutation_authorized": False,
        }

    @router.post("/{notification_id}/read")
    def mark_read(
        notification_id: str, request: Request,
        session_id: str | None = Header(
            default=None, alias="X-ARMS-Local-Test-Session",
        ),
    ):
        return transition(request, session_id, notification_id, "read")

    @router.post("/{notification_id}/acknowledge")
    def acknowledge(
        notification_id: str, request: Request,
        session_id: str | None = Header(
            default=None, alias="X-ARMS-Local-Test-Session",
        ),
    ):
        return transition(request, session_id, notification_id, "acknowledge")

    @router.post("/{notification_id}/snooze")
    def snooze(
        notification_id: str, request: Request,
        session_id: str | None = Header(
            default=None, alias="X-ARMS-Local-Test-Session",
        ),
    ):
        return transition(request, session_id, notification_id, "snooze")

    @router.post("/{notification_id}/dismiss")
    def dismiss(
        notification_id: str, request: Request,
        session_id: str | None = Header(
            default=None, alias="X-ARMS-Local-Test-Session",
        ),
    ):
        return transition(request, session_id, notification_id, "dismiss")

    return router

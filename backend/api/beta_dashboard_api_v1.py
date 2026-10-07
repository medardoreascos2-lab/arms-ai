"""Authenticated, read-only Beta Dashboard V1 API."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.dashboard.beta_dashboard_projection_v1 import BetaDashboardProjectionV1
from backend.security.beta_access_v1 import (
    BetaAccessDeniedError,
    BetaAuthenticationError,
    BetaUserIdentity,
    BetaUserStoreV1,
)


BETA_SESSION_COOKIE = "arms_beta_session_v1"
BETA_CSRF_HEADER = "X-ARMS-BETA-CSRF"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class CreateBetaUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=1024)
    role: Literal["beta_user", "disabled"] = "beta_user"
    beta_days: int = Field(default=30, ge=1, le=3650)


class SetBetaUserStatusRequest(BaseModel):
    enabled: bool


class ExtendBetaRequest(BaseModel):
    days: int = Field(ge=1, le=3650)


def create_beta_dashboard_router_v1(
    *,
    user_store: BetaUserStoreV1 | None = None,
    projection: BetaDashboardProjectionV1 | None = None,
    live_data_service: Any = None,
) -> APIRouter:
    projection = projection or BetaDashboardProjectionV1()
    router = APIRouter(prefix="/api/v1/beta", tags=["Beta Dashboard V1"])

    def store_for(request: Request) -> BetaUserStoreV1:
        store = user_store or getattr(request.app.state, "beta_user_store_v1", None)
        if not isinstance(store, BetaUserStoreV1):
            raise HTTPException(status_code=503, detail="beta_auth_not_configured")
        return store

    def live_service_for(request: Request) -> Any:
        return live_data_service or getattr(
            request.app.state, "dashboard_live_data_service_v2", None
        )

    def require_identity(
        request: Request,
        session_token: str | None = Cookie(default=None, alias=BETA_SESSION_COOKIE),
    ) -> BetaUserIdentity:
        try:
            return store_for(request).resolve_session(session_token)
        except BetaAuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from None
        except BetaAccessDeniedError as exc:
            raise HTTPException(status_code=403, detail=exc.reason) from None

    def require_admin(
        identity: BetaUserIdentity = Depends(require_identity),
    ) -> BetaUserIdentity:
        if identity.role != "admin":
            raise HTTPException(status_code=403, detail="admin_role_required")
        return identity

    def require_csrf(
        request: Request,
        session_token: str | None = Cookie(default=None, alias=BETA_SESSION_COOKIE),
        csrf_token: str | None = Header(default=None, alias=BETA_CSRF_HEADER),
    ) -> None:
        try:
            store_for(request).require_csrf(session_token, csrf_token)
        except BetaAccessDeniedError as exc:
            raise HTTPException(status_code=403, detail=exc.reason) from None

    @router.post("/auth/login")
    def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
        try:
            session = store_for(request).authenticate(
                email=payload.email,
                password=payload.password,
            )
        except (BetaAuthenticationError, ValueError):
            raise HTTPException(status_code=401, detail="invalid_credentials") from None
        except BetaAccessDeniedError as exc:
            raise HTTPException(status_code=403, detail=exc.reason) from None
        response.set_cookie(
            key=BETA_SESSION_COOKIE,
            value=session.token,
            max_age=12 * 60 * 60,
            httponly=True,
            secure=store_for(request).cookie_secure,
            samesite="strict",
            path="/api/v1/beta",
        )
        response.headers["Cache-Control"] = "no-store"
        return {
            "user": session.user.to_public_dict(),
            "session_expires_at": session.expires_at,
            "csrf_token": session.csrf_token,
        }

    @router.get("/auth/me")
    def me(
        request: Request,
        response: Response,
        identity: BetaUserIdentity = Depends(require_identity),
        session_token: str | None = Cookie(default=None, alias=BETA_SESSION_COOKIE),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return {
            "user": identity.to_public_dict(),
            "csrf_token": store_for(request).rotate_csrf(str(session_token)),
        }

    @router.post("/auth/logout")
    def logout(
        request: Request,
        response: Response,
        _identity: BetaUserIdentity = Depends(require_identity),
        _csrf: None = Depends(require_csrf),
        session_token: str | None = Cookie(default=None, alias=BETA_SESSION_COOKIE),
    ) -> dict[str, bool]:
        store_for(request).logout(session_token)
        response.delete_cookie(BETA_SESSION_COOKIE, path="/api/v1/beta")
        response.headers["Cache-Control"] = "no-store"
        return {"logged_out": True}

    def read_bundle(request: Request) -> dict[str, Any]:
        service = live_service_for(request)
        if service is None or not callable(getattr(service, "get_snapshot", None)):
            raise HTTPException(status_code=503, detail="beta_read_model_unavailable")
        return projection.build(request.app.state, service)

    @router.get("/dashboard")
    def dashboard(
        request: Request,
        response: Response,
        _identity: BetaUserIdentity = Depends(require_identity),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return read_bundle(request)

    @router.get("/live")
    def live(
        request: Request,
        response: Response,
        _identity: BetaUserIdentity = Depends(require_identity),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        bundle = read_bundle(request)
        return {
            "contract_version": bundle["contract_version"],
            "observed_at": bundle["observed_at"],
            "paper_only": True,
            "live": bundle["live"],
        }

    @router.get("/history")
    def history(
        request: Request,
        response: Response,
        _identity: BetaUserIdentity = Depends(require_identity),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        bundle = read_bundle(request)
        return {
            "contract_version": bundle["contract_version"],
            "observed_at": bundle["observed_at"],
            "paper_only": True,
            "history": bundle["history"],
        }

    @router.get("/performance")
    def performance(
        request: Request,
        response: Response,
        _identity: BetaUserIdentity = Depends(require_identity),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        bundle = read_bundle(request)
        return {
            "contract_version": bundle["contract_version"],
            "observed_at": bundle["observed_at"],
            "paper_only": True,
            "performance": bundle["performance"],
        }

    @router.get("/admin/users")
    def list_users(
        request: Request,
        response: Response,
        _admin: BetaUserIdentity = Depends(require_admin),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return store_for(request).list_users()

    @router.post("/admin/users", status_code=201)
    def create_user(
        payload: CreateBetaUserRequest,
        request: Request,
        _admin: BetaUserIdentity = Depends(require_admin),
        _csrf: None = Depends(require_csrf),
    ) -> dict[str, Any]:
        try:
            user = store_for(request).create_user(
                email=payload.email,
                password=payload.password,
                role=payload.role,
                beta_days=payload.beta_days,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return {"user": user.to_public_dict()}

    @router.patch("/admin/users/{user_id}/status")
    def set_status(
        user_id: str,
        payload: SetBetaUserStatusRequest,
        request: Request,
        _admin: BetaUserIdentity = Depends(require_admin),
        _csrf: None = Depends(require_csrf),
    ) -> dict[str, Any]:
        try:
            user = store_for(request).set_enabled(user_id, enabled=payload.enabled)
        except KeyError:
            raise HTTPException(status_code=404, detail="beta_user_not_found") from None
        except BetaAccessDeniedError as exc:
            raise HTTPException(status_code=409, detail=exc.reason) from None
        return {"user": user.to_public_dict()}

    @router.post("/admin/users/{user_id}/extend")
    def extend_access(
        user_id: str,
        payload: ExtendBetaRequest,
        request: Request,
        _admin: BetaUserIdentity = Depends(require_admin),
        _csrf: None = Depends(require_csrf),
    ) -> dict[str, Any]:
        try:
            user = store_for(request).extend_beta(user_id, days=payload.days)
        except KeyError:
            raise HTTPException(status_code=404, detail="beta_user_not_found") from None
        except (BetaAccessDeniedError, ValueError) as exc:
            detail = exc.reason if isinstance(exc, BetaAccessDeniedError) else str(exc)
            raise HTTPException(status_code=409, detail=detail) from None
        return {"user": user.to_public_dict()}

    return router

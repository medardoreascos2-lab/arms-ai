"""Evaluation-only API for source-backed prop-firm policies.

This router is intentionally not registered in the operational application.
It owns no broker, PAPER, portfolio, journal, or account mutation dependency.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, NoReturn

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder

from backend.api.schemas.prop_firm_policy import (
    AccountPolicyEvaluationRequest,
    MultiAccountPolicyEvaluationRequest,
)
from backend.prop_firms import (
    AccountStage,
    AmbiguousProfileError,
    ProfileNotFoundError,
    ProfileRegistryError,
    ProfileSourceStatusError,
    PropFirmProfileRegistry,
    SourceStatus,
    canonical_profile_registry,
    evaluate_accounts,
)


def _response(value: Any) -> Any:
    return jsonable_encoder(
        value,
        custom_encoder={Decimal: str, Enum: lambda item: item.value},
    )


def _raise_transport_error(exc: ValueError) -> NoReturn:
    if isinstance(exc, ProfileNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (AmbiguousProfileError, ProfileSourceStatusError)):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=422, detail=str(exc)) from exc


def create_prop_firm_policy_router(
    registry: PropFirmProfileRegistry | None = None,
) -> APIRouter:
    """Create an isolated policy router backed only by immutable evaluation data."""
    selected_registry = registry or canonical_profile_registry()
    if not isinstance(selected_registry, PropFirmProfileRegistry):
        raise ValueError("registry must be a PropFirmProfileRegistry")

    router = APIRouter(prefix="/api/v1/prop-firms", tags=["prop-firm-policy"])

    @router.get("/profiles")
    def list_profiles(
        at: datetime,
        firm_id: str | None = None,
        source_status: SourceStatus | None = None,
    ) -> Any:
        try:
            profiles = selected_registry.list_supported_profiles(
                at, firm_id=firm_id, source_status=source_status,
            )
        except ValueError as exc:
            _raise_transport_error(exc)
        return _response({"profiles": profiles, "count": len(profiles), "as_of": at})

    @router.get("/profiles/resolve")
    def resolve_profile(
        firm_id: str,
        program_id: str,
        stage: AccountStage,
        account_size: Decimal,
        at: datetime,
        version: str | None = None,
        allow_unverified: bool = Query(default=False),
    ) -> Any:
        required_status = None if allow_unverified else SourceStatus.CURRENT_VERIFIED
        try:
            resolved = selected_registry.resolve_profile(
                firm_id,
                program_id,
                stage,
                account_size,
                at,
                version=version,
                required_source_status=required_status,
            )
        except ProfileRegistryError as exc:
            _raise_transport_error(exc)
        except ValueError as exc:
            _raise_transport_error(exc)
        return _response(resolved)

    @router.post("/evaluate/account")
    def evaluate_account(request: AccountPolicyEvaluationRequest) -> Any:
        try:
            snapshot = request.snapshot.to_domain()
            payout_requests = (
                {}
                if request.payout_request is None
                else {snapshot.account_id: request.payout_request.to_domain()}
            )
            summary = evaluate_accounts(
                selected_registry,
                (snapshot,),
                payout_requests=payout_requests,
                require_current_sources=request.require_current_sources,
            )
        except ValueError as exc:
            _raise_transport_error(exc)
        return _response(summary.accounts[0])

    @router.post("/evaluate/accounts")
    def evaluate_multiple_accounts(
        request: MultiAccountPolicyEvaluationRequest,
    ) -> Any:
        try:
            snapshots = tuple(item.to_domain() for item in request.snapshots)
            payout_requests = {
                account_id: item.to_domain()
                for account_id, item in request.payout_requests.items()
            }
            summary = evaluate_accounts(
                selected_registry,
                snapshots,
                payout_requests=payout_requests,
                require_current_sources=request.require_current_sources,
            )
        except ValueError as exc:
            _raise_transport_error(exc)
        return _response(summary)

    return router


router = create_prop_firm_policy_router()

"""FastAPI dependency for privileged administrative operations."""

from __future__ import annotations

from fastapi import (
    Header,
    HTTPException,
    Request,
    status,
)

from backend.security.admin_authorization_v2 import (
    AdminAuthorizationV2,
)


ADMIN_TOKEN_HEADER = "X-ARMS-ADMIN-TOKEN"


def require_admin_authorization_v2(
    request: Request,
    x_arms_admin_token: str | None = Header(
        default=None,
        alias=ADMIN_TOKEN_HEADER,
    ),
) -> None:
    """
    Fail closed unless the configured administrative authority
    explicitly authorizes the supplied credential.
    """

    authority = getattr(
        request.app.state,
        "admin_authorization_v2",
        None,
    )

    if not isinstance(
        authority,
        AdminAuthorizationV2,
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_authorization_not_configured",
        )

    try:
        authority.require_authorized(
            x_arms_admin_token
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin_unauthorized",
        ) from None

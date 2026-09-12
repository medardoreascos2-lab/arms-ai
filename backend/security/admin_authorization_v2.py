"""Administrative API authorization authority."""

from __future__ import annotations

from secrets import compare_digest


class AdminAuthorizationV2:
    """
    Fail-closed authority for privileged API operations.

    The administrative credential is intentionally separate
    from external market-data/webhook credentials.
    """

    def __init__(
        self,
        *,
        token: str,
    ) -> None:
        if not isinstance(token, str):
            raise TypeError(
                "token must be a string"
            )

        normalized = token.strip()

        if not normalized:
            raise ValueError(
                "admin token must not be empty"
            )

        self._token = normalized

    def is_authorized(
        self,
        provided_token: str | None,
    ) -> bool:
        if not isinstance(
            provided_token,
            str,
        ):
            return False

        normalized = provided_token.strip()

        if not normalized:
            return False

        return compare_digest(
            normalized,
            self._token,
        )

    def require_authorized(
        self,
        provided_token: str | None,
    ) -> None:
        if not self.is_authorized(
            provided_token
        ):
            raise PermissionError(
                "admin_unauthorized"
            )

from fastapi import APIRouter, Request

from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)


router = APIRouter(
    prefix="/api/v2/dashboard/account",
    tags=["account"],
)


def _get_manager(
    request: Request,
) -> AccountConfigManagerV2:

    manager = getattr(
        request.app.state,
        "account_config_manager_v2",
        None,
    )

    if not isinstance(
        manager,
        AccountConfigManagerV2,
    ):
        raise RuntimeError(
            "AccountConfigManagerV2 runtime "
            "no disponible."
        )

    return manager


@router.get("")
def get_active_account(
    request: Request,
):

    manager = _get_manager(request)
    profile = manager.get_active_account()

    return {
        "account":
            manager.get_active_account_name(),
        "balance":
            profile.account_size,
        "risk_percent":
            profile.risk_percent,
        "daily_loss_limit":
            profile.daily_loss_limit,
        "max_drawdown":
            profile.max_drawdown,
    }

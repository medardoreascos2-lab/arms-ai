from fastapi import APIRouter

from backend.risk.account_config_manager_v1 import (
    AccountConfigManagerV1,
)


router = APIRouter(
    prefix="/api/v2/dashboard/account",
    tags=["account"],
)


manager = AccountConfigManagerV1()


@router.get("")
def get_active_account():

    profile = (
        manager.get_profile()
    )

    return {
        "account": profile.name,
        "balance": profile.account_balance,
        "risk_percent": profile.risk_percent,
        "daily_loss_limit": profile.daily_loss_limit,
        "max_drawdown": profile.max_drawdown,
    }

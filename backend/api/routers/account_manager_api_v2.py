from fastapi import APIRouter

from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)


router = APIRouter(
    prefix="/api/v2/dashboard/account-manager",
    tags=["account-manager"],
)


manager = AccountConfigManagerV2()



@router.get("")
def get_account_manager():

    account = (
        manager
        .get_active_account()
    )


    return {

        "active_account":
            manager.active_account,

        "firm":
            account.firm_name,

        "account_size":
            account.account_size,

        "profit_target":
            account.profit_target,

        "daily_loss_limit":
            account.daily_loss_limit,

        "max_drawdown":
            account.max_drawdown,

        "risk_percent":
            account.risk_percent,

        "platform":
            account.platform,

    }



@router.get("/available")
def get_available_accounts():

    return {

        "accounts":
            manager
            .get_available_accounts()

    }



@router.post("/switch")
def switch_account(
    account_name: str,
):

    account = (
        manager
        .set_active_account(
            account_name
        )
    )


    return {

        "status":
            "ACCOUNT_CHANGED",

        "active_account":
            account_name,

        "account_size":
            account.account_size,

    }

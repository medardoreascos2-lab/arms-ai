from fastapi import APIRouter

from backend.risk.account_switcher_v1 import (
    AccountSwitcherV1,
)


router = APIRouter(
    prefix="/api/v2/dashboard/account",
    tags=["account"],
)


switcher = AccountSwitcherV1()


@router.post("/switch")
def switch_account(
    account_name: str,
):

    return (
        switcher
        .switch_account(
            account_name
        )
    )

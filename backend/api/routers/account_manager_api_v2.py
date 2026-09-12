from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from backend.api.schemas.account_switch_v2 import AccountSwitchRequestV2
from backend.services.account_switch_safety_v2 import AccountSwitchSafetyV2, AccountSwitchRejected

from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)


router = APIRouter(
    prefix="/api/v2/dashboard/account-manager",
    tags=["account-manager"],
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
def get_account_manager(
    request: Request,
):

    manager = _get_manager(request)

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
def get_available_accounts(
    request: Request,
):

    manager = _get_manager(request)

    return {

        "accounts":
            manager
            .get_available_accounts()

    }



def _get_switch_safety(request: Request) -> AccountSwitchSafetyV2:
    safety = getattr(request.app.state, "account_switch_safety_v2", None)
    if not isinstance(safety, AccountSwitchSafetyV2):
        raise HTTPException(status_code=503, detail="No se puede verificar la identidad del runtime.")
    return safety


@router.get("/switch-context")
def get_switch_context(request: Request):
    try:
        return _get_switch_safety(request).context()
    except (ValueError, AttributeError, KeyError, TypeError, OSError):
        raise HTTPException(status_code=409, detail="La identidad del runtime requiere revisión.") from None


@router.post("/switch")
def switch_account(payload: AccountSwitchRequestV2, request: Request):
    safety = _get_switch_safety(request)
    try:
        return safety.switch(account_id=payload.account_id, profile_name=payload.profile_name)
    except AccountSwitchRejected as exc:
        return JSONResponse(status_code=409, content={
            "status": "ACCOUNT_SWITCH_REJECTED",
            "changed": False,
            "reason": str(exc),
            "detail": "No se cambió la cuenta. El cambio requiere un runtime coherente, sin actividad pendiente y una transición coordinada.",
        })

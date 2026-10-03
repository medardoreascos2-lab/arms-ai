"""Source-backed Topstep profiles reviewed 2026-10-03.

Profiles are pure configuration. They do not authorize trading or payouts.
XFA profiles deliberately fail closed on contract exposure because the current
official scaling-tier table is not available as text.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from .models_v1 import (
    AccountStage, ConsistencyApplication, ConsistencyMode, ConsistencyPolicy,
    ContractLimitEnforcement, ContractLimitPolicy, DailyLossEnforcement,
    DailyLossPolicy, DrawdownModel, DrawdownPolicy, DrawdownTransition,
    ExposureWeight, PayoutFractionBasis, PayoutPolicy, PayoutTier,
    PropFirmProfile, ReferenceUpdateMode, ResetBoundary, SourceEvidence,
    SourceReview, SourceStatus, TradingDayPolicy, ValueBasis,
    WeightedExposurePolicy,
)

REVIEWED_AT = datetime(2026, 10, 3, 7, 40, tzinfo=timezone.utc)
EFFECTIVE_FROM = REVIEWED_AT
VERSION = "2026-10-03"

PROGRAM = "https://help.topstep.com/en/articles/8284099-topstep-program-overview"
COMBINE = "https://help.topstep.com/en/articles/8284197-trading-combine-parameters"
MLL = "https://help.topstep.com/en/articles/8284204-what-is-the-maximum-loss-limit"
CONSISTENCY = "https://help.topstep.com/en/articles/8284208-consistency-at-topstep"
DLL = "https://help.topstep.com/en/articles/10490293-daily-loss-limit-in-the-trading-combine-and-express-funded-account"
XFA = "https://help.topstep.com/en/articles/8284215-express-funded-account-parameters"
SCALING = "https://help.topstep.com/en/articles/8284223-what-is-the-scaling-plan"
PAYOUT = "https://help.topstep.com/en/articles/8284233-topstep-payout-policy"
PRODUCTS = "https://help.topstep.com/en/articles/8284206-when-and-what-products-can-i-trade"
LIVE = "https://help.topstep.com/en/articles/10657969-live-funded-account-parameters"
PRO = "https://help.topstep.com/en/articles/14645398-what-is-a-pro-account"

SIZES = (D("50000"), D("100000"), D("150000"))
PROFIT_TARGETS = {D("50000"): D("3000"), D("100000"): D("6000"), D("150000"): D("9000")}
MAXIMUM_LOSSES = {D("50000"): D("2000"), D("100000"): D("3000"), D("150000"): D("4500")}
MAXIMUM_MINIS = {D("50000"): D("5"), D("100000"): D("10"), D("150000"): D("15")}
DAILY_LOSSES = {D("50000"): D("1000"), D("100000"): D("2000"), D("150000"): D("3000")}
STANDARD_CAPS = {D("50000"): D("2000"), D("100000"): D("3000"), D("150000"): D("5000")}
CONSISTENCY_CAPS = {D("50000"): D("3000"), D("100000"): D("4000"), D("150000"): D("6000")}


def _source(url: str, title: str, heading: str, *, temporary: bool = False) -> SourceEvidence:
    return SourceEvidence(url, title, REVIEWED_AT, rule_heading=heading,
                          temporary=temporary, review_required=temporary)


BASE_SOURCES = (
    _source(PROGRAM, "Topstep Program Overview", "Three stages"),
    _source(MLL, "What is the Maximum Loss Limit?", "How the MLL works"),
)
COMBINE_SOURCES = BASE_SOURCES + (
    _source(COMBINE, "Trading Combine Parameters", "Rules, objectives, maximum position size"),
    _source(CONSISTENCY, "Consistency at Topstep", "Trading Combine - Consistency Target (55%)"),
    _source(DLL, "Daily Loss Limit", "Optional DLL parameters"),
    _source(PRODUCTS, "When and What Products Can I Trade?", "Permitted Products"),
)
XFA_SOURCES = BASE_SOURCES + (
    _source(XFA, "Express Funded Account Parameters", "Standard vs. Consistency"),
    _source(CONSISTENCY, "Consistency at Topstep", "XFA Consistency Objective (40%)"),
    _source(DLL, "Daily Loss Limit", "Optional DLL parameters"),
    _source(SCALING, "What is the Scaling Plan?", "How It Works"),
    _source(PAYOUT, "Topstep Payout Policy", "XFA payout paths"),
)
PROMO_SOURCE = _source(PAYOUT, "Topstep Payout Policy",
                       "Limited Time Offering: Payout Cap Increase", temporary=True)


def _review(status: SourceStatus, sources: tuple[SourceEvidence, ...], *, temporary: bool = False) -> SourceReview:
    return SourceReview(status, REVIEWED_AT, sources,
                        REVIEWED_AT + (timedelta(days=1) if temporary else timedelta(days=30)))


def _size(value: D) -> D:
    if value not in SIZES:
        raise ValueError("unsupported Topstep standard account size")
    return value


def _daily(size: D, enabled: bool) -> DailyLossPolicy:
    if not enabled:
        return DailyLossPolicy(None, DailyLossEnforcement.NOT_APPLICABLE)
    return DailyLossPolicy(DAILY_LOSSES[size], DailyLossEnforcement.SESSION_BLOCK,
                           ResetBoundary.TRADING_DAY_END)


def _combine_exposure(size: D) -> ContractLimitPolicy:
    mini = ("ES", "NQ", "RTY", "YM", "GC", "CL")
    micro = ("MES", "MNQ", "M2K", "MYM", "MGC", "MCL")
    weights = tuple(ExposureWeight(symbol, D("1")) for symbol in mini)
    weights += tuple(ExposureWeight(symbol, D("0.1")) for symbol in micro)
    return ContractLimitPolicy(
        None, weighted_exposure=WeightedExposurePolicy(MAXIMUM_MINIS[size], weights),
        breach_enforcement=ContractLimitEnforcement.TRADING_BLOCK,
    )


def _mll(size: D, starting_balance: D, *, post_payout: bool) -> DrawdownPolicy:
    transition = DrawdownTransition(False, 1, D("0")) if post_payout else None
    return DrawdownPolicy(
        DrawdownModel.TRAILING_END_OF_DAY, MAXIMUM_LOSSES[size],
        ValueBasis.MIN_BALANCE_OR_EQUITY, D("0") if starting_balance == 0 else starting_balance,
        transition, ReferenceUpdateMode.END_OF_DAY_BALANCE,
    )


def trading_combine_profile(account_size: D, *, dll_enabled: bool = False) -> PropFirmProfile:
    size = _size(account_size)
    suffix = "dll" if dll_enabled else "no-dll"
    return PropFirmProfile(
        firm_id="topstep", program_id="trading_combine", stage=AccountStage.EVALUATION,
        version=f"{VERSION}/{suffix}", effective_from=EFFECTIVE_FROM,
        account_size=size, starting_balance=size, drawdown=_mll(size, size, post_payout=False),
        daily_loss=_daily(size, dll_enabled), contract_limit=_combine_exposure(size),
        consistency=ConsistencyPolicy(True, D("0.55"), D("0.01"), ConsistencyMode.TOTAL_PROFIT),
        payout=PayoutPolicy(False), trading_days=TradingDayPolicy(2),
        profit_target=PROFIT_TARGETS[size], source_reference=COMBINE,
        source_review=_review(SourceStatus.CURRENT_VERIFIED, COMBINE_SOURCES),
    )


def _xfa_contracts() -> ContractLimitPolicy:
    return ContractLimitPolicy(
        None, breach_enforcement=ContractLimitEnforcement.TRADING_BLOCK,
        unavailable_reason="SCALING_PLAN_TIER_DATA_UNAVAILABLE",
    )


def _xfa_payout(size: D, *, consistency: bool, promotional_cap: bool) -> PayoutPolicy:
    cap = (CONSISTENCY_CAPS if consistency else STANDARD_CAPS)[size]
    if promotional_cap:
        cap *= 2
    tiers = (
        PayoutTier(0, maximum_amount=cap),
        PayoutTier(1, maximum_amount=cap, minimum_profit_since_last_payout=D("0.01")),
    )
    return PayoutPolicy(
        True, maximum_payout_amount=cap, maximum_payout_fraction=D("0.5"),
        minimum_winning_days_per_cycle=0 if consistency else 5,
        minimum_trading_days_per_cycle=3 if consistency else 0,
        minimum_payout_amount=D("125"),
        maximum_fraction_basis=PayoutFractionBasis.CURRENT_BALANCE,
        tiers=tiers if not consistency else (), consistency_per_cycle=consistency,
    )


def _xfa_profile(account_size: D, *, consistency: bool, dll_enabled: bool,
                 promotional_cap: bool) -> PropFirmProfile:
    size = _size(account_size)
    path = "consistency" if consistency else "standard"
    dll = "dll" if dll_enabled else "no-dll"
    promo = "/temporary-promo" if promotional_cap else ""
    sources = XFA_SOURCES + ((PROMO_SOURCE,) if promotional_cap else ())
    return PropFirmProfile(
        firm_id="topstep", program_id=f"express_funded_{path}", stage=AccountStage.EXPRESS,
        version=f"{VERSION}/{dll}{promo}", effective_from=EFFECTIVE_FROM,
        account_size=size, starting_balance=D("0"), allow_zero_starting_balance=True,
        drawdown=_mll(size, D("0"), post_payout=True), daily_loss=_daily(size, dll_enabled),
        contract_limit=_xfa_contracts(),
        consistency=(ConsistencyPolicy(True, D("0.40"), D("0.01"),
                                       ConsistencyMode.TOTAL_PROFIT,
                                       ConsistencyApplication.PAYOUT_CYCLE)
                     if consistency else ConsistencyPolicy(False)),
        payout=_xfa_payout(size, consistency=consistency, promotional_cap=promotional_cap),
        source_reference=XFA,
        source_review=_review(SourceStatus.INCOMPLETE, sources, temporary=promotional_cap),
    )


def express_funded_standard_profile(account_size: D, *, dll_enabled: bool = False,
                                    promotional_cap: bool = False) -> PropFirmProfile:
    return _xfa_profile(account_size, consistency=False, dll_enabled=dll_enabled,
                        promotional_cap=promotional_cap)


def express_funded_consistency_profile(account_size: D, *, dll_enabled: bool = False,
                                       promotional_cap: bool = False) -> PropFirmProfile:
    return _xfa_profile(account_size, consistency=True, dll_enabled=dll_enabled,
                        promotional_cap=promotional_cap)


@dataclass(frozen=True)
class TopstepProgramSupport:
    program_id: str
    stage: AccountStage
    source_status: SourceStatus
    implemented: bool
    reason: str | None
    source_url: str


TOPSTEP_PROGRAM_SUPPORT = (
    TopstepProgramSupport("trading_combine", AccountStage.EVALUATION,
                          SourceStatus.CURRENT_VERIFIED, True, None, COMBINE),
    TopstepProgramSupport("express_funded_standard", AccountStage.EXPRESS,
                          SourceStatus.INCOMPLETE, True,
                          "SCALING_PLAN_TIER_DATA_UNAVAILABLE", XFA),
    TopstepProgramSupport("express_funded_consistency", AccountStage.EXPRESS,
                          SourceStatus.INCOMPLETE, True,
                          "SCALING_PLAN_TIER_DATA_UNAVAILABLE", XFA),
    TopstepProgramSupport("live_funded", AccountStage.LIVE, SourceStatus.INCOMPLETE, False,
                          "DYNAMIC_STARTING_BALANCE_AND_RISK_TIERS_UNSUPPORTED", LIVE),
    TopstepProgramSupport("pro_account", AccountStage.PRO, SourceStatus.INCOMPLETE, False,
                          "TRANSFER_DEPENDENT_STARTING_BALANCE_AND_SCALING_UNSUPPORTED", PRO),
)


def standard_topstep_profiles() -> tuple[PropFirmProfile, ...]:
    profiles = []
    for size in SIZES:
        profiles.extend((
            trading_combine_profile(size), trading_combine_profile(size, dll_enabled=True),
            express_funded_standard_profile(size),
            express_funded_standard_profile(size, dll_enabled=True),
            express_funded_consistency_profile(size),
            express_funded_consistency_profile(size, dll_enabled=True),
        ))
    return tuple(profiles)

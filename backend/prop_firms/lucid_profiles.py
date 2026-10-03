"""Source-backed Lucid Trading profiles reviewed 2026-10-03.

These profiles are pure, read-only policy configuration. LucidLive remains an
explicitly unsupported transition and this module never grants LIVE execution
authority. Current profiles are fail-closed while allowed-hours state is not
represented by the generic account snapshot.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from .models_v1 import (
    AccountStage, ConsistencyApplication, ConsistencyMode, ConsistencyPolicy,
    ContractLimitEnforcement, ContractLimitPolicy, DailyLossEnforcement,
    DailyLossPolicy, DrawdownModel, DrawdownPolicy, ExposureWeight, PayoutPolicy,
    PayoutTier, PropFirmProfile, ReferenceUpdateMode, ResetBoundary,
    SourceEvidence, SourceReview, SourceStatus, TradingDayPolicy, ValueBasis,
    WeightedExposurePolicy,
)

REVIEWED_AT = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)
EFFECTIVE_FROM = datetime(2025, 11, 28, 20, 0, tzinfo=timezone.utc)
VERSION = "2026-10-03"

EVALUATION_RULES = "https://support.lucidtrading.com/en/articles/12890029-lucidpro-evaluation-account"
FUNDED_RULES = "https://support.lucidtrading.com/en/articles/12890069-lucidpro-funded-account"
DAILY_LOSS_RULES = "https://support.lucidtrading.com/en/articles/12890122-lucidpro-daily-loss-limit"
DRAWDOWN_RULES = "https://support.lucidtrading.com/en/articles/12890136-lucidpro-drawdown"
PAYOUT_RULES = "https://support.lucidtrading.com/en/articles/12890092-lucidpro-payouts"
CONSISTENCY_RULES = "https://support.lucidtrading.com/en/articles/12890109-lucidpro-consistency-percentage"
PRODUCTS = "https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions"
TRADING_TIMES = "https://support.lucidtrading.com/en/articles/11404729-allowed-trading-times"
LIVE_RULES = "https://support.lucidtrading.com/en/articles/13425130-new-live-structure"
FLEX_RULES = "https://support.lucidtrading.com/en/articles/12945790-lucidflex-evaluation-account"
DIRECT_RULES = "https://support.lucidtrading.com/en/articles/12890164-luciddirect-payout-objectives"
DAILY_RULES = "https://support.lucidtrading.com/en/articles/15997244-luciddaily-funded-account"
MAXX_RULES = "https://support.lucidtrading.com/en/articles/14315460-lucidmaxx-eval-rules"
BLACK_RULES = "https://support.lucidtrading.com/en/articles/13424906-lucidblack-drawdown"

SIZES = (D("25000"), D("50000"), D("100000"), D("150000"))
PROFIT_TARGETS = {
    D("25000"): D("1250"), D("50000"): D("3000"),
    D("100000"): D("6000"), D("150000"): D("9000"),
}
MAXIMUM_LOSSES = {
    D("25000"): D("1000"), D("50000"): D("2000"),
    D("100000"): D("3000"), D("150000"): D("4500"),
}
FIXED_DAILY_LOSSES = {
    D("25000"): None, D("50000"): D("1200"),
    D("100000"): D("1800"), D("150000"): D("2700"),
}
INITIAL_TRAIL_BALANCES = {
    size: size + MAXIMUM_LOSSES[size] + D("100") for size in SIZES
}
MAXIMUM_UNITS = {
    D("25000"): D("2"), D("50000"): D("4"),
    D("100000"): D("6"), D("150000"): D("10"),
}
MINIMUM_CYCLE_PROFIT = {
    D("25000"): D("250"), D("50000"): D("500"),
    D("100000"): D("750"), D("150000"): D("1000"),
}
FIRST_PAYOUT_CAP = {
    D("25000"): D("1000"), D("50000"): D("2000"),
    D("100000"): D("2500"), D("150000"): D("3000"),
}
LATER_PAYOUT_CAP = {
    D("25000"): D("1500"), D("50000"): D("2500"),
    D("100000"): D("3000"), D("150000"): D("3500"),
}

MICRO_PRODUCTS = ("MES", "MNQ", "M2K", "MYM", "MCL", "MGC", "SIL")
STANDARD_PRODUCTS = (
    "ES", "NQ", "RTY", "NKD", "YM", "6A", "6B", "6C", "6E", "6J",
    "6S", "6N", "CL", "QM", "QG", "NG", "PL", "HG", "GC", "SI",
    "HE", "LE", "ZS", "ZC", "ZL", "ZM", "ZW",
)


def _source(url: str, title: str, heading: str) -> SourceEvidence:
    return SourceEvidence(url, title, REVIEWED_AT, rule_heading=heading)


COMMON_SOURCES = (
    _source(DRAWDOWN_RULES, "LucidPro Drawdown", "End of Day Drawdown"),
    _source(DAILY_LOSS_RULES, "LucidPro Daily Loss Limit", "Daily Loss Limit"),
    _source(PRODUCTS, "Approved Products and Commissions", "Approved products"),
    _source(TRADING_TIMES, "Allowed Trading Times", "LucidPro accounts"),
)
EVALUATION_SOURCES = (
    _source(EVALUATION_RULES, "LucidPro Evaluation Account", "Evaluation account overview"),
) + COMMON_SOURCES
FUNDED_SOURCES = (
    _source(FUNDED_RULES, "LucidPro Funded Account", "Funded account overview"),
    _source(PAYOUT_RULES, "LucidPro Payouts", "Payout eligibility criteria"),
    _source(CONSISTENCY_RULES, "LucidPro Consistency Percentage", "40 percent calculation"),
) + COMMON_SOURCES


def _review(sources: tuple[SourceEvidence, ...], *, conflict: bool = False) -> SourceReview:
    status = SourceStatus.SOURCE_CONFLICT if conflict else SourceStatus.INCOMPLETE
    return SourceReview(status, REVIEWED_AT, sources, REVIEWED_AT + timedelta(days=30))


def _size(value: D) -> D:
    if value not in SIZES:
        raise ValueError("unsupported Lucid account size")
    return value


def _exposure(size: D) -> ContractLimitPolicy:
    weights = tuple(ExposureWeight(symbol, D("1")) for symbol in STANDARD_PRODUCTS)
    weights += tuple(ExposureWeight(symbol, D("0.1")) for symbol in MICRO_PRODUCTS)
    return ContractLimitPolicy(
        None,
        weighted_exposure=WeightedExposurePolicy(MAXIMUM_UNITS[size], weights),
        breach_enforcement=ContractLimitEnforcement.ACCOUNT_FAIL,
    )


def _drawdown(size: D) -> DrawdownPolicy:
    return DrawdownPolicy(
        DrawdownModel.TRAILING_END_OF_DAY,
        MAXIMUM_LOSSES[size],
        ValueBasis.BALANCE,
        floor_cap=size + D("100"),
        reference_update_mode=ReferenceUpdateMode.END_OF_DAY_BALANCE,
    )


def _fixed_daily_loss(size: D) -> DailyLossPolicy:
    limit = FIXED_DAILY_LOSSES[size]
    if limit is None:
        return DailyLossPolicy(None, DailyLossEnforcement.NOT_APPLICABLE)
    return DailyLossPolicy(
        limit, DailyLossEnforcement.SESSION_BLOCK, ResetBoundary.SESSION_END,
    )


def _payout(size: D) -> PayoutPolicy:
    return PayoutPolicy(
        True,
        minimum_balance=INITIAL_TRAIL_BALANCES[size],
        minimum_profit_since_last_payout=MINIMUM_CYCLE_PROFIT[size],
        minimum_payout_amount=D("500"),
        maximum_payout_count=5,
        trader_profit_fraction=D("0.90"),
        tiers=(
            PayoutTier(0, maximum_amount=FIRST_PAYOUT_CAP[size]),
            PayoutTier(1, maximum_amount=LATER_PAYOUT_CAP[size]),
        ),
        consistency_per_cycle=True,
    )


def evaluation_profile(account_size: D) -> PropFirmProfile:
    size = _size(account_size)
    return PropFirmProfile(
        firm_id="lucid", program_id="lucidpro_evaluation",
        stage=AccountStage.EVALUATION, version=VERSION,
        effective_from=EFFECTIVE_FROM, account_size=size, starting_balance=size,
        drawdown=_drawdown(size), daily_loss=_fixed_daily_loss(size),
        contract_limit=_exposure(size), consistency=ConsistencyPolicy(False),
        payout=PayoutPolicy(False), trading_days=TradingDayPolicy(0),
        profit_target=PROFIT_TARGETS[size], source_reference=EVALUATION_RULES,
        source_review=_review(EVALUATION_SOURCES),
    )


def funded_no_dll_profile(account_size: D) -> PropFirmProfile:
    size = _size(account_size)
    return _funded_profile(
        size, "lucidpro_funded_no_dll",
        DailyLossPolicy(None, DailyLossEnforcement.NOT_APPLICABLE),
    )


def funded_fixed_dll_profile(account_size: D) -> PropFirmProfile:
    size = _size(account_size)
    # The funded overview lists $600 for 25K while the dedicated DLL source says None.
    daily_loss = (_fixed_daily_loss(size) if size != D("25000")
                  else DailyLossPolicy(D("600"), DailyLossEnforcement.SESSION_BLOCK))
    return _funded_profile(
        size, "lucidpro_funded_fixed_dll", daily_loss,
        conflict=size == D("25000"),
    )


def funded_scaling_dll_profile(account_size: D) -> PropFirmProfile:
    size = _size(account_size)
    return _funded_profile(
        size,
        "lucidpro_funded_scaling_dll",
        DailyLossPolicy(
            FIXED_DAILY_LOSSES[size], DailyLossEnforcement.SESSION_BLOCK,
            ResetBoundary.SESSION_END, D("0.60"), INITIAL_TRAIL_BALANCES[size],
        ),
    )


def _funded_profile(
    size: D, program_id: str, daily_loss: DailyLossPolicy, *, conflict: bool = False,
) -> PropFirmProfile:
    return PropFirmProfile(
        firm_id="lucid", program_id=program_id, stage=AccountStage.FUNDED,
        version=VERSION, effective_from=EFFECTIVE_FROM,
        account_size=size, starting_balance=size, drawdown=_drawdown(size),
        daily_loss=daily_loss, contract_limit=_exposure(size),
        consistency=ConsistencyPolicy(
            True, D("0.40"), D("0.01"), ConsistencyMode.TOTAL_PROFIT,
            ConsistencyApplication.PAYOUT_CYCLE, maximum_is_inclusive=True,
        ),
        payout=_payout(size), source_reference=FUNDED_RULES,
        source_review=_review(FUNDED_SOURCES, conflict=conflict),
    )


@dataclass(frozen=True)
class LucidProgramSupport:
    program_id: str
    stage: AccountStage
    next_stage: AccountStage | None
    source_status: SourceStatus
    executable: bool
    reason: str
    source_url: str


LUCID_PROGRAM_SUPPORT = (
    LucidProgramSupport(
        "lucidpro_evaluation", AccountStage.EVALUATION, AccountStage.FUNDED,
        SourceStatus.INCOMPLETE, False, "ALLOWED_TRADING_TIME_STATE_UNMODELED",
        TRADING_TIMES,
    ),
    LucidProgramSupport(
        "lucidpro_funded", AccountStage.FUNDED, AccountStage.LIVE,
        SourceStatus.INCOMPLETE, False,
        "ALLOWED_TRADING_TIME_STATE_UNMODELED_AND_LIVE_TRANSITION_DISCRETIONARY",
        TRADING_TIMES,
    ),
    LucidProgramSupport(
        "lucidlive", AccountStage.LIVE, None, SourceStatus.INCOMPLETE, False,
        "LIVE_EXECUTION_UNSUPPORTED_AND_TRANSITION_DISCRETIONARY", LIVE_RULES,
    ),
    LucidProgramSupport(
        "lucidflex", AccountStage.UNKNOWN, None, SourceStatus.INCOMPLETE, False,
        "PROFILE_NOT_YET_NORMALIZED", FLEX_RULES,
    ),
    LucidProgramSupport(
        "luciddirect", AccountStage.UNKNOWN, None, SourceStatus.INCOMPLETE, False,
        "PROFILE_NOT_YET_NORMALIZED", DIRECT_RULES,
    ),
    LucidProgramSupport(
        "luciddaily", AccountStage.UNKNOWN, None, SourceStatus.INCOMPLETE, False,
        "NEWS_WINDOW_AND_INTRADAY_RULES_UNMODELED", DAILY_RULES,
    ),
    LucidProgramSupport(
        "lucidmaxx", AccountStage.UNKNOWN, AccountStage.LIVE,
        SourceStatus.INCOMPLETE, False, "DIRECT_LIVE_ROUTE_UNSUPPORTED", MAXX_RULES,
    ),
    LucidProgramSupport(
        "lucidblack_legacy", AccountStage.UNKNOWN, None,
        SourceStatus.INCOMPLETE, False, "LEGACY_PROGRAM_KEPT_SEPARATE", BLACK_RULES,
    ),
)


def standard_lucid_profiles() -> tuple[PropFirmProfile, ...]:
    factories = (
        evaluation_profile, funded_no_dll_profile,
        funded_fixed_dll_profile, funded_scaling_dll_profile,
    )
    return tuple(factory(size) for size in SIZES for factory in factories)
